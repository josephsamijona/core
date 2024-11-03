
import json
import datetime
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

# Importations pour la gestion des cartes NFC
from smartcard.System import readers
from smartcard.util import toHexString
from smartcard.Exceptions import CardConnectionException, NoCardException

# Importations pour la capture de la caméra et la détection des QR codes
import cv2
from pyzbar.pyzbar import decode
from PIL import Image

from membership_management.models import (
    CardInfo, 
    PassengerUser, 
    Subscription,
    BoardingValidation, 
    BoardingError,
    ValidationRule
)
from transport_management.models import Trip, TransactionScan
from .device_manager import get_device, ensure_single_active_session
from .sync_manager import store_offline_validation

# ------------------------------
# Exceptions Personnalisées
# ------------------------------
class ValidationError(Exception):
    """Exception personnalisée pour les erreurs de validation"""
    pass

class NFCError(ValidationError):
    """Exception pour les erreurs spécifiques NFC"""
    pass

class QRCodeError(ValidationError):
    """Exception pour les erreurs spécifiques QR"""
    pass

# ------------------------------
# Fonctions Utilitaires NFC
# ------------------------------

def get_uid(connection):
    """Récupère l'UID d'une carte NFC"""
    get_uid_command = [0xFF, 0xCA, 0x00, 0x00, 0x00]
    try:
        response, sw1, sw2 = connection.transmit(get_uid_command)
        if sw1 == 0x90 and sw2 == 0x00:
            uid = toHexString(response)
            return uid.replace(' ', '').upper()
        else:
            raise NFCError(f"Erreur lecture UID: SW1={sw1:02X}, SW2={sw2:02X}")
    except (NoCardException, CardConnectionException) as e:
        raise NFCError(f"Erreur lecture NFC: {str(e)}")

def read_card():
    """Lit les données d'une carte NFC"""
    try:
        available_readers = readers()
        if not available_readers:
            return {"error": "Aucun lecteur de carte n'a été trouvé. Veuillez brancher un lecteur."}

        reader = available_readers[0]
        connection = reader.createConnection()
        connection.connect()

        uid = get_uid(connection)
        if not uid:
            return {"error": "Impossible de lire l'UID de la carte."}

        card_data = {
            "uid": uid,
            "read_time": timezone.now().isoformat()
        }

        return card_data

    except (NoCardException, CardConnectionException) as e:
        return {"error": f"Erreur de connexion au lecteur : {e}"}
    except Exception as e:
        return {"error": f"Erreur inconnue : {e}"}

# ------------------------------
# Fonctions QR Code
# ------------------------------

def decode_qr_data_from_image(image):
    """Décode les données d'un QR code depuis une image"""
    try:
        decoded_objects = decode(Image.fromarray(image))
        if not decoded_objects:
            return None
        
        qr_content = decoded_objects[0].data.decode('utf-8')
        return qr_content

    except Exception as e:
        raise QRCodeError(f"Erreur décodage QR: {str(e)}")

def capture_and_decode_qr_code():
    """Capture et décode un QR code via la caméra"""
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise QRCodeError("Impossible d'ouvrir la caméra")

        print("Appuyez sur 'q' pour quitter la capture.")

        while True:
            ret, frame = cap.read()
            if not ret:
                raise QRCodeError("Erreur de capture d'image")

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            qr_content = decode_qr_data_from_image(gray)
            
            if qr_content:
                cap.release()
                cv2.destroyAllWindows()
                return qr_content

            cv2.imshow('Capture du QR Code', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        return None

    except Exception as e:
        if cap:
            cap.release()
        cv2.destroyAllWindows()
        raise QRCodeError(f"Erreur capture QR: {str(e)}")

# ------------------------------
# Validation Core
# ------------------------------

def validate_nfc_card(card_data):
    """Valide une carte NFC avec les règles métier"""
    uid = card_data.get('uid')
    if not uid:
        return {"status": "failure", "message": "UID manquant dans les données de la carte."}

    try:
        card_info = CardInfo.objects.get(card_uid=uid)
        passenger = card_info.passenger

        # Contexte de validation
        validation_context = {
            'passenger_id': passenger.id,
            'card_type': 'nfc',
            'trip_id': card_data.get('trip_id'),
            'validation_time': timezone.now()
        }

        # Validation des règles
        rules_result = validate_rules(validation_context)
        if not rules_result['is_valid']:
            return {
                "status": "failure",
                "message": "Violation des règles de validation",
                "violations": rules_result['violations']
            }

        # Vérifications standard
        if not check_subscription(passenger.id):
            return {"status": "failure", "message": "Abonnement inactif ou expiré."}

        if not validate_passenger_type(passenger.id):
            return {"status": "failure", "message": "Passager non autorisé."}

        # Vérification des doublons
        if is_duplicate_scan(passenger.id, card_data.get('trip_id'), timezone.now()):
            return {"status": "failure", "message": "Doublon de validation détecté."}

        return {
            "status": "success",
            "message": "Validation réussie.",
            "passenger_id": passenger.id,
            "trip_id": card_data.get('trip_id'),
            "warnings": rules_result.get('warnings', [])
        }

    except ObjectDoesNotExist:
        return {"status": "failure", "message": "Carte non reconnue."}
    except Exception as e:
        handle_validation_exception(e, validation_context)
        return {"status": "failure", "message": "Erreur lors de la validation de la carte."}

def validate_qr_code(qr_data):
    """Valide un code QR avec les règles métier"""
    try:
        data = json.loads(qr_data)
        passenger_id = data.get('passenger_id')
        trip_id = data.get('trip_id')

        if not passenger_id or not trip_id:
            return {"status": "failure", "message": "Données QR invalides."}

        validation_context = {
            'passenger_id': passenger_id,
            'trip_id': trip_id,
            'validation_type': 'qr',
            'validation_time': timezone.now()
        }

        # Validation des règles
        rules_result = validate_rules(validation_context)
        if not rules_result['is_valid']:
            return {
                "status": "failure",
                "message": "Violation des règles de validation",
                "violations": rules_result['violations']
            }

        if not check_subscription(passenger_id):
            return {"status": "failure", "message": "Abonnement inactif ou expiré."}

        if not validate_passenger_type(passenger_id):
            return {"status": "failure", "message": "Passager non autorisé."}

        if not check_capacity_limits(trip_id):
            return {"status": "failure", "message": "Capacité maximale atteinte."}

        if is_duplicate_scan(passenger_id, trip_id, timezone.now()):
            return {"status": "failure", "message": "Doublon de validation détecté."}

        return {
            "status": "success",
            "message": "Validation réussie.",
            "passenger_id": passenger_id,
            "trip_id": trip_id,
            "warnings": rules_result.get('warnings', [])
        }

    except json.JSONDecodeError:
        return {"status": "failure", "message": "Format QR invalide."}
    except Exception as e:
        handle_validation_exception(e, {'qr_data': qr_data})
        return {"status": "failure", "message": "Erreur lors de la validation du QR code."}

def validate_qr_code_from_camera():
    """Capture et valide un QR code via la caméra"""
    qr_data = capture_and_decode_qr_code()
    if qr_data:
        return validate_qr_code(qr_data)
    return {"status": "failure", "message": "Aucun QR code détecté."}

# ------------------------------
# Validation des Règles
# ------------------------------

def validate_rules(validation_context):
    """Valide l'ensemble des règles métier"""
    try:
        rules = ValidationRule.objects.filter(active=True).order_by('priority')
        
        validation_results = {
            'is_valid': True,
            'violations': [],
            'warnings': []
        }

        for rule in rules:
            result = check_rule(rule, validation_context)
            if not result['is_valid']:
                if rule.rule_definition.get('blocking', True):
                    validation_results['violations'].append(result['message'])
                    validation_results['is_valid'] = False
                else:
                    validation_results['warnings'].append(result['message'])

        return validation_results

    except Exception as e:
        raise ValidationError(f"Erreur validation règles: {str(e)}")

def check_rule(rule, context):
    """Vérifie une règle spécifique"""
    try:
        if rule.rule_type == 'boarding':
            return check_boarding_rule(context, rule.rule_definition)
        elif rule.rule_type == 'capacity':
            return check_capacity_rule(context, rule.rule_definition)
        elif rule.rule_type == 'timing':
            return check_timing_rule(context, rule.rule_definition)
        
        return {'is_valid': True, 'message': ''}

    except Exception as e:
        return {'is_valid': False, 'message': str(e)}

def check_boarding_rule(context, rule_definition):
    """Vérifie les règles d'embarquement"""
    try:
        passenger_id = context.get('passenger_id')
        trip_id = context.get('trip_id')

        if not all([passenger_id, trip_id]):
            return {'is_valid': False, 'message': 'Données embarquement incomplètes'}

        if not verify_stop_sequence(trip_id, context.get('stop_id')):
            return {'is_valid': False, 'message': 'Séquence d\'arrêt invalide'}

        return {'is_valid': True, 'message': ''}

    except Exception as e:
        return {'is_valid': False, 'message': str(e)}

def check_capacity_rule(context, rule_definition):
    """Vérifie les règles de capacité"""
    try:
        trip = Trip.objects.get(id=context.get('trip_id'))
        max_capacity = rule_definition.get('max_capacity', trip.capacity)
        
        if trip.current_passenger_count >= max_capacity:
            return {'is_valid': False, 'message': 'Capacité maximale atteinte'}

        return {'is_valid': True, 'message': ''}

    except Exception as e:
        return {'is_valid': False, 'message': str(e)}

def check_timing_rule(context, rule_definition):
    """Vérifie les règles temporelles"""
    try:
        trip = Trip.objects.get(id=context.get('trip_id'))
        current_time = timezone.now()

        if current_time < trip.start_time:
            return {'is_valid': False, 'message': 'Trop tôt pour la validation'}
            
        if current_time > trip.end_time:
            return {'is_valid': False, 'message': 'Trop tard pour la validation'}

        return {'is_valid': True, 'message': ''}

    except Exception as e:
        return {'is_valid': False, 'message': str(e)}

# ------------------------------
# Vérifications Métier
# ------------------------------

def check_subscription(passenger_id):
    """Vérifie si le passager a un abonnement actif"""
    try:
        return Subscription.objects.filter(
            passenger_id=passenger_id,
            status='active',
            expiration_date__gte=timezone.now()
        ).exists()
    except Exception as e:
        handle_validation_exception(e)
        return False

def validate_passenger_type(passenger_id):
    """Valide le type de passager"""
    try:
        passenger = PassengerUser.objects.get(id=passenger_id)
        if getattr(passenger, 'is_banned', False):
            return False
        return True
    except Exception as e:
        handle_validation_exception(e)
        return False

def verify_stop_sequence(trip_id, stop_id):
    """Vérifie la séquence des arrêts"""
    try:
        if not stop_id:
            return True  # Si pas d'arrêt spécifié, on considère valide
        
        trip = Trip.objects.get(id=trip_id)
        # Votre logique de vérification de séquence d'arrêts
        return True
    except Exception as e:
        handle_validation_exception(e)
        return False

def check_capacity_limits(trip_id):
    """Vérifie les limites de capacité"""
    try:
        trip = Trip.objects.get(id=trip_id)
        return trip.current_passenger_count < trip.capacity
    except Exception as e:
        handle_validation_exception(e)
        return False

# ------------------------------
# Gestion des Erreurs
# ------------------------------

def handle_validation_exception(exception, context=None):
    """Gestion centralisée des erreurs de validation"""
    error_data = {
        'error_type': exception.__class__.__name__,
        'error_message': str(exception),
        'context': context or {},
        'timestamp': timezone.now()
    }

    try:
        BoardingError.objects.create(
            error_type='validation',
            error_details=error_data,
            timestamp=error_data['timestamp']
        )
        print(f"Erreur de validation: {error_data}")
    except Exception as e:
        print(f"Erreur lors de l'enregistrement de l'erreur: {e}")

def log_validation_error(error_info):
    """Enregistre une erreur de validation"""
    try:
        BoardingError.objects.create(
            error_message=error_info.get('error_message', 'Erreur inconnue'),
            additional_info=error_info.get('additional_info', ''),
            timestamp=timezone.now()
        )
    except Exception as e:
            print(f"Erreur lors de l'enregistrement de l'erreur de validation : {e}")

# ------------------------------
# Gestion des Doublons et Validations Hors-ligne
# ------------------------------

def is_duplicate_scan(passenger_id, trip_id, scan_time):
    """
    Vérifie si un scan est un doublon.
    
    Args:
        passenger_id: ID du passager
        trip_id: ID du voyage
        scan_time: Heure du scan
    """
    time_threshold = scan_time - datetime.timedelta(minutes=5)
    return TransactionScan.objects.filter(
        passenger_id=passenger_id,
        trip_id=trip_id,
        timestamp__gte=time_threshold
    ).exists()

def create_validation_record(context):
    """
    Crée un enregistrement de validation.
    
    Args:
        context: Contexte de validation
    """
    with transaction.atomic():
        validation = BoardingValidation.objects.create(
            passenger_id=context['passenger_id'],
            validation_type=context.get('validation_type', 'unknown'),
            validation_time=timezone.now(),
            validation_details=context,
            validation_status='pending'
        )
        return validation

def process_offline_validation(validation_data):
    """
    Traite une validation effectuée en mode hors-ligne.
    
    Args:
        validation_data: Données de validation
    """
    try:
        # Stocker la validation hors-ligne
        stored = store_offline_validation({
            'data': validation_data,
            'timestamp': timezone.now().isoformat(),
            'status': 'pending'
        })
        
        if not stored:
            raise ValidationError("Échec du stockage de la validation hors-ligne")

        # Créer l'enregistrement de validation
        validation_context = {
            'passenger_id': validation_data.get('passenger_id'),
            'trip_id': validation_data.get('trip_id'),
            'validation_type': validation_data.get('validation_type'),
            'offline': True
        }
        
        create_validation_record(validation_context)
        
        return {
            'status': 'success',
            'message': 'Validation hors-ligne enregistrée',
            'offline': True
        }

    except Exception as e:
        handle_validation_exception(e, validation_data)
        return {
            'status': 'failure',
            'message': 'Erreur lors de la validation hors-ligne',
            'error': str(e)
        }

def validate_offline_data(offline_data):
    """
    Valide les données stockées hors-ligne.
    
    Args:
        offline_data: Données à valider
    """
    try:
        validation_type = offline_data.get('validation_type')
        if validation_type == 'nfc':
            return validate_nfc_card(offline_data)
        elif validation_type == 'qr':
            return validate_qr_code(offline_data.get('qr_data'))
        else:
            raise ValidationError(f"Type de validation non supporté: {validation_type}")
    except Exception as e:
        handle_validation_exception(e, offline_data)
        return {
            'status': 'failure',
            'message': 'Erreur validation données hors-ligne',
            'error': str(e)
        }

# ------------------------------
# Fonction Principale
# ------------------------------

def process_validation(validation_type, validation_data, context=None):
    """
    Point d'entrée principal pour toutes les validations.
    
    Args:
        validation_type: Type de validation ('nfc' ou 'qr')
        validation_data: Données à valider
        context: Contexte additionnel
    """
    try:
        # Vérification initiale du contexte
        if context and check_duplicate_validation(context):
            return {"status": "failure", "message": "Validation en double détectée"}

        # Mode hors-ligne
        if context and context.get('offline', False):
            return process_offline_validation({
                'validation_type': validation_type,
                **validation_data,
                **context
            })

        # Validation en ligne
        if validation_type == 'nfc':
            return validate_nfc_card(validation_data)
        elif validation_type == 'qr':
            return validate_qr_code(validation_data)
        else:
            raise ValidationError(f"Type de validation non supporté: {validation_type}")

    except Exception as e:
        handle_validation_exception(e, context)
        return {
            "status": "failure",
            "message": "Erreur lors de la validation",
            "error": str(e)
        }

def check_duplicate_validation(context):
    """
    Vérifie si une validation similaire existe récemment.
    
    Args:
        context: Contexte de validation
    """
    time_threshold = timezone.now() - datetime.timedelta(minutes=5)
    return BoardingValidation.objects.filter(
        passenger_id=context['passenger_id'],
        validation_time__gte=time_threshold
    ).exists()

# ------------------------------
# Utilitaires de Test
# ------------------------------

def simulate_validation(validation_type, test_data):
    """
    Simule une validation pour les tests.
    
    Args:
        validation_type: Type de validation à simuler
        test_data: Données de test
    """
    try:
        return process_validation(validation_type, test_data, {'test_mode': True})
    except Exception as e:
        return {
            'status': 'failure',
            'message': 'Erreur lors de la simulation',
            'error': str(e)
        }