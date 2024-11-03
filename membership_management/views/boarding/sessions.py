from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views import View
from django.core.exceptions import ValidationError

from .events import (
    BoardingEvent,
    BoardingEventType,
    get_event_dispatcher,
    BoardingEventHandler
)

from membership_management.views.boarding.boarding_utils.device_manager import (
    get_device,
    ensure_single_active_session,
    validate_device_context,
    start_device_session,
    end_device_session
)

from membership_management.models import (
    BoardingSession,
    BoardingError,
    
)
from transport_management.models import Trip
class SessionError(Exception):
    """Exception personnalisée pour les erreurs de session"""
    pass

class BoardingSessionManager:
    """Gestionnaire des sessions de boarding"""
    
    def __init__(self):
        self.event_dispatcher = get_event_dispatcher()
        self.active_sessions = {}

    @transaction.atomic
    def initialize_session(self, device_id: str, trip_id: str, driver_id: str):
        """
        Initialise une nouvelle session de boarding.
        """
        try:
            # Vérification du contexte
            if not validate_device_context(device_id, driver_id, trip_id):
                raise SessionError("Contexte de session invalide")

            # Vérification des sessions existantes
            ensure_single_active_session(device_id)

            # Récupération des informations du voyage
            trip = Trip.objects.select_related('route', 'driver').get(id=trip_id)

            # Création de la session
            session = start_device_session(device_id, trip_id)

            # Enregistrement dans le cache des sessions actives
            self.active_sessions[session.session_id] = {
                'device_id': device_id,
                'trip_id': trip_id,
                'started_at': timezone.now()
            }

            # Dispatch de l'événement d'initialisation
            self.event_dispatcher.dispatch(BoardingEvent(
                type=BoardingEventType.SESSION_INITIALIZED,
                data={
                    'session_id': session.session_id,
                    'device_id': device_id,
                    'trip_id': trip_id,
                    'driver_id': driver_id
                }
            ))

            return session

        except Trip.DoesNotExist:
            raise SessionError("Voyage non trouvé")
        except Exception as e:
            raise SessionError(f"Erreur d'initialisation: {str(e)}")

    @transaction.atomic
    def end_session(self, session_id: str):
        """
        Termine une session de boarding.
        """
        try:
            session = BoardingSession.objects.get(session_id=session_id)
            
            if session.status not in ['active', 'paused']:
                raise SessionError("La session n'est pas active")

            # Mise à jour de la session
            end_device_session(session_id)

            # Retrait du cache
            self.active_sessions.pop(session_id, None)

            # Dispatch de l'événement de fin
            self.event_dispatcher.dispatch(BoardingEvent(
                type=BoardingEventType.SESSION_ENDED,
                data={
                    'session_id': session_id,
                    'end_time': timezone.now().isoformat()
                }
            ))

            return True

        except BoardingSession.DoesNotExist:
            raise SessionError("Session non trouvée")
        except Exception as e:
            raise SessionError(f"Erreur de terminaison: {str(e)}")

    def pause_session(self, session_id: str, reason: str = None):
        """
        Met en pause une session.
        """
        try:
            session = BoardingSession.objects.get(session_id=session_id)
            session.status = 'paused'
            session.save()

            self.event_dispatcher.dispatch(BoardingEvent(
                type=BoardingEventType.SESSION_PAUSED,
                data={
                    'session_id': session_id,
                    'reason': reason
                }
            ))

        except BoardingSession.DoesNotExist:
            raise SessionError("Session non trouvée")

    def resume_session(self, session_id: str):
        """
        Reprend une session en pause.
        """
        try:
            session = BoardingSession.objects.get(session_id=session_id)
            session.status = 'active'
            session.save()

            self.event_dispatcher.dispatch(BoardingEvent(
                type=BoardingEventType.SESSION_RESUMED,
                data={'session_id': session_id}
            ))

        except BoardingSession.DoesNotExist:
            raise SessionError("Session non trouvée")

    def get_session_status(self, session_id: str):
        """
        Récupère le statut complet d'une session.
        """
        try:
            session = BoardingSession.objects.select_related('trip').get(
                session_id=session_id
            )
            
            trip = session.trip
            return {
                'session_id': session_id,
                'status': session.status,
                'trip_info': {
                    'trip_id': trip.id,
                    'route': trip.route.name,
                    'current_stop': trip.current_stop.name if trip.current_stop else None,
                    'passenger_count': trip.current_passenger_count,
                    'capacity': trip.capacity
                },
                'started_at': session.start_time,
                'device_id': session.device_id,
                'is_offline': session.offline_mode
            }

        except BoardingSession.DoesNotExist:
            raise SessionError("Session non trouvée")

    def validate_session(self, session_id: str):
        """
        Valide qu'une session est utilisable.
        """
        try:
            session = BoardingSession.objects.get(session_id=session_id)
            if session.status != 'active':
                raise SessionError("Session inactive")
            
            if session.end_time and session.end_time < timezone.now():
                raise SessionError("Session expirée")
                
            return True

        except BoardingSession.DoesNotExist:
            raise SessionError("Session non trouvée")

# Views pour l'API
class BoardingSessionView(View):
    session_manager = BoardingSessionManager()

    def post(self, request):
        """Initialise une nouvelle session"""
        try:
            data = request.POST
            session = self.session_manager.initialize_session(
                device_id=data.get('device_id'),
                trip_id=data.get('trip_id'),
                driver_id=data.get('driver_id')
            )
            
            return JsonResponse({
                'status': 'success',
                'session_id': session.session_id,
                'message': 'Session initialisée avec succès'
            })

        except SessionError as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': 'Erreur interne du serveur'
            }, status=500)

    def delete(self, request, session_id):
        """Termine une session"""
        try:
            self.session_manager.end_session(session_id)
            return JsonResponse({
                'status': 'success',
                'message': 'Session terminée avec succès'
            })

        except SessionError as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': 'Erreur interne du serveur'
            }, status=500)

    def get(self, request, session_id):
        """Récupère le statut d'une session"""
        try:
            status = self.session_manager.get_session_status(session_id)
            return JsonResponse({
                'status': 'success',
                'data': status
            })

        except SessionError as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': 'Erreur interne du serveur'
            }, status=500)

# Handler des événements de session
class SessionEventHandler(BoardingEventHandler):
    def register_handlers(self):
        self.dispatcher.subscribe(
            BoardingEventType.SESSION_INITIALIZED,
            self.handle_session_initialized
        )
        self.dispatcher.subscribe(
            BoardingEventType.SESSION_ENDED,
            self.handle_session_ended
        )
        self.dispatcher.subscribe(
            BoardingEventType.DEVICE_ERROR,
            self.handle_device_error
        )

    def handle_session_initialized(self, event: BoardingEvent):
        """Gère l'initialisation d'une session"""
        try:
            # Logique additionnelle post-initialisation
            pass
        except Exception as e:
            self.log_error("Session initialization handler error", e, event)

    def handle_session_ended(self, event: BoardingEvent):
        """Gère la fin d'une session"""
        try:
            # Logique de nettoyage post-session
            pass
        except Exception as e:
            self.log_error("Session end handler error", e, event)

    def handle_device_error(self, event: BoardingEvent):
        """Gère les erreurs de device dans une session"""
        try:
            session_id = event.data.get('session_id')
            if session_id:
                # Potentiellement mettre la session en pause
                session_manager = BoardingSessionManager()
                session_manager.pause_session(
                    session_id,
                    reason=f"Device error: {event.data.get('error_message')}"
                )
        except Exception as e:
            self.log_error("Device error handler error", e, event)

    def log_error(self, message: str, error: Exception, event: BoardingEvent = None):
        """Enregistre une erreur de handling"""
        try:
            BoardingError.objects.create(
                error_type='session_handler_error',
                error_details={
                    'message': message,
                    'error': str(error),
                    'event': event.data if event else None
                }
            )
        except Exception as e:
            print(f"Error logging failed: {e}")

# Initialisation du handler
session_handler = SessionEventHandler(get_event_dispatcher())