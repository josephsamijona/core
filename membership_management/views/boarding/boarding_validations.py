
from django.http import JsonResponse
from django.views import View
from django.db import transaction
from django.utils import timezone

# Import des utilitaires existants
from membership_management.views.boarding.boarding_utils.validations import (
    validate_nfc_card,
    validate_qr_code,
    process_validation,
    handle_validation_exception,
    create_validation_record,
    process_offline_validation,
    is_duplicate_scan
)

from membership_management.views.boarding.boarding_utils.device_manager import get_device
from membership_management.views.boarding.boarding_utils.sync_manager import store_offline_validation

from .events import (
    BoardingEvent,
    BoardingEventType,
    get_event_dispatcher,
    BoardingEventHandler
)

from membership_management.models import (
    BoardingSession,
    BoardingValidation,
    PassengerTrip,
    BoardingError,
    Trip
)

class BoardingValidationError(Exception):
    """Exception spécifique pour les erreurs de validation boarding"""
    pass

class BoardingValidationManager:
    """
    Gestionnaire des validations de boarding - Utilise les utilitaires de validation existants
    """
    
    def __init__(self):
        self.event_dispatcher = get_event_dispatcher()

    @transaction.atomic
    def validate_boarding(self, session_id: str, validation_type: str, validation_data: dict):
        """
        Point d'entrée principal pour la validation de boarding
        """
        try:
            # Vérification de la session
            session = self._get_active_session(session_id)
            
            # Construction du contexte de validation
            validation_context = {
                'session_id': session_id,
                'trip_id': session.trip.id,
                'validation_time': timezone.now(),
                'validation_type': validation_type
            }

            # Dispatch de l'événement début de validation
            self._dispatch_validation_start(validation_type, validation_context)

            # Utilisation des utilitaires de validation existants
            validation_result = process_validation(
                validation_type,
                validation_data,
                validation_context
            )

            if validation_result['status'] != 'success':
                self._handle_validation_failure(session, validation_result)
                return validation_result

            # Création des enregistrements boarding
            passenger_trip = self._create_passenger_boarding(
                session,
                validation_result
            )

            # Mise à jour des compteurs et statuts
            self._update_trip_status(session.trip, passenger_trip)

            # Dispatch de l'événement succès
            self._dispatch_validation_success(validation_result, passenger_trip)

            return {
                'status': 'success',
                'message': 'Embarquement validé',
                'passenger_trip_id': passenger_trip.id,
                'warnings': validation_result.get('warnings', [])
            }

        except BoardingValidationError as e:
            return {
                'status': 'failure',
                'message': str(e)
            }
        except Exception as e:
            handle_validation_exception(e, validation_context)
            return {
                'status': 'error',
                'message': 'Erreur système lors de la validation'
            }

    @transaction.atomic
    def process_alighting(self, session_id: str, passenger_trip_id: str):
        """
        Gère la descente d'un passager
        """
        try:
            session = self._get_active_session(session_id)
            passenger_trip = PassengerTrip.objects.get(id=passenger_trip_id)

            if passenger_trip.status != 'boarded':
                raise BoardingValidationError("Statut de voyage invalide pour la descente")

            # Enregistrement de la descente
            passenger_trip.status = 'alighted'
            passenger_trip.alighting_time = timezone.now()
            passenger_trip.save()

            # Mise à jour du compteur de passagers
            self._update_passenger_count(session.trip, increment=False)

            # Dispatch de l'événement descente
            self._dispatch_alighting_event(passenger_trip)

            return {
                'status': 'success',
                'message': 'Descente enregistrée'
            }

        except (BoardingValidationError, PassengerTrip.DoesNotExist) as e:
            return {
                'status': 'failure',
                'message': str(e)
            }
        except Exception as e:
            handle_validation_exception(e)
            return {
                'status': 'error',
                'message': 'Erreur système'
            }

    def _get_active_session(self, session_id: str) -> BoardingSession:
        """Vérifie et retourne une session active"""
        try:
            session = BoardingSession.objects.get(session_id=session_id)
            if session.status != 'active':
                raise BoardingValidationError("Session inactive")
            return session
        except BoardingSession.DoesNotExist:
            raise BoardingValidationError("Session non trouvée")

    @transaction.atomic
    def _create_passenger_boarding(self, session, validation_result):
        """Crée les enregistrements liés au boarding"""
        try:
            passenger_id = validation_result['passenger_id']

            # Création de l'enregistrement PassengerTrip
            passenger_trip = PassengerTrip.objects.create(
                trip=session.trip,
                passenger_id=passenger_id,
                boarding_time=timezone.now(),
                status='boarded',
                boarding_validation=create_validation_record({
                    'passenger_id': passenger_id,
                    'validation_type': validation_result.get('validation_type', 'unknown'),
                    'session_id': session.session_id
                })
            )

            return passenger_trip

        except Exception as e:
            raise BoardingValidationError(f"Erreur création boarding: {str(e)}")

    def _update_trip_status(self, trip: Trip, passenger_trip: PassengerTrip):
        """Met à jour les statuts et compteurs du voyage"""
        self._update_passenger_count(trip, increment=True)
        
        # Autres mises à jour du statut du voyage si nécessaire
        if trip.status == 'scheduled' and not trip.start_time:
            trip.status = 'in_progress'
            trip.start_time = timezone.now()
            trip.save()

    def _update_passenger_count(self, trip: Trip, increment: bool = True):
        """Met à jour le compteur de passagers"""
        if increment:
            trip.current_passenger_count += 1
        else:
            if trip.current_passenger_count > 0:
                trip.current_passenger_count -= 1
        trip.save()

    def _dispatch_validation_start(self, validation_type, context):
        """Dispatch l'événement début de validation"""
        event_type = BoardingEventType.CARD_SCANNED if validation_type == 'nfc' else BoardingEventType.QR_SCANNED
        self.event_dispatcher.dispatch(BoardingEvent(
            type=event_type,
            data=context
        ))

    def _dispatch_validation_success(self, validation_result, passenger_trip):
        """Dispatch l'événement succès de validation"""
        self.event_dispatcher.dispatch(BoardingEvent(
            type=BoardingEventType.VALIDATION_SUCCEEDED,
            data={
                'validation_result': validation_result,
                'passenger_trip_id': passenger_trip.id
            }
        ))

    def _dispatch_alighting_event(self, passenger_trip):
        """Dispatch l'événement de descente"""
        self.event_dispatcher.dispatch(BoardingEvent(
            type=BoardingEventType.PASSENGER_ALIGHTED,
            data={
                'passenger_trip_id': passenger_trip.id,
                'trip_id': passenger_trip.trip_id,
                'alighting_time': timezone.now().isoformat()
            }
        ))

    def _handle_validation_failure(self, session, validation_result):
        """Gère l'échec de validation"""
        self.event_dispatcher.dispatch(BoardingEvent(
            type=BoardingEventType.VALIDATION_FAILED,
            data={
                'session_id': session.session_id,
                'reason': validation_result.get('message', 'Échec de validation'),
                'details': validation_result
            }
        ))

class BoardingValidationView(View):
    def __init__(self):
        self.validation_manager = BoardingValidationManager()

    def post(self, request, session_id):
        """Endpoint de validation boarding"""
        try:
            validation_type = request.POST.get('type')
            validation_data = request.POST.get('data')

            if not validation_type or not validation_data:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Données de validation manquantes'
                }, status=400)

            result = self.validation_manager.validate_boarding(
                session_id,
                validation_type,
                validation_data
            )

            return JsonResponse(result)

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

class PassengerAlightingView(View):
    def __init__(self):
        self.validation_manager = BoardingValidationManager()

    def post(self, request, session_id, passenger_trip_id):
        """Endpoint de descente passager"""
        try:
            result = self.validation_manager.process_alighting(
                session_id,
                passenger_trip_id
            )
            return JsonResponse(result)

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

# Handler d'événements
class BoardingValidationHandler(BoardingEventHandler):
    def register_handlers(self):
        self.dispatcher.subscribe(
            BoardingEventType.VALIDATION_SUCCEEDED,
            self.handle_validation_success
        )
        self.dispatcher.subscribe(
            BoardingEventType.VALIDATION_FAILED,
            self.handle_validation_failure
        )
        self.dispatcher.subscribe(
            BoardingEventType.PASSENGER_ALIGHTED,
            self.handle_passenger_alighting
        )

    def handle_validation_success(self, event: BoardingEvent):
        """Gestion post-validation réussie"""
        try:
            # Logique additionnelle après validation réussie
            pass
        except Exception as e:
            self._log_handler_error("Success handler error", e, event)

    def handle_validation_failure(self, event: BoardingEvent):
        """Gestion des échecs de validation"""
        try:
            # Logique de gestion des échecs
            pass
        except Exception as e:
            self._log_handler_error("Failure handler error", e, event)

    def handle_passenger_alighting(self, event: BoardingEvent):
        """Gestion post-descente"""
        try:
            # Logique après descente passager
            pass
        except Exception as e:
            self._log_handler_error("Alighting handler error", e, event)

    def _log_handler_error(self, message: str, error: Exception, event: BoardingEvent):
        """Log les erreurs de handling"""
        try:
            BoardingError.objects.create(
                error_type='validation_handler_error',
                error_details={
                    'message': message,
                    'error': str(error),
                    'event_data': event.data
                }
            )
        except Exception as e:
            print(f"Error logging failed: {e}")

# Initialisation du handler
validation_handler = BoardingValidationHandler(get_event_dispatcher())
