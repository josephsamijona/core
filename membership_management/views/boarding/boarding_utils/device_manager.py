from membership_management.models import BoardingDevice, BoardingSession, BoardingError
from django.utils import timezone
from django.db import transaction

class DeviceError(Exception):
    """Exception personnalisée pour les erreurs liées aux dispositifs"""
    pass

def get_device(device_id):
    """
    Récupère les informations d'un dispositif en fonction de son identifiant.
    """
    try:
        device = BoardingDevice.objects.get(device_id=device_id)
        return device
    except BoardingDevice.DoesNotExist:
        return None

def ensure_single_active_session(device_id):
    """
    Vérifie qu'un dispositif n'a qu'une seule session active à la fois.
    Si une session active existe déjà pour ce dispositif, elle est terminée.
    """
    active_sessions = BoardingSession.objects.filter(device__device_id=device_id, status='active')
    if active_sessions.exists():
        for session in active_sessions:
            session.status = 'ended'
            session.end_time = timezone.now()
            session.save()

def validate_device_specs(device_specs):
    """
    Valide les spécifications du dispositif.
    """
    required_specs = ['model', 'os_version', 'app_version']
    
    if not device_specs or not isinstance(device_specs, dict):
        return False
        
    return all(spec in device_specs for spec in required_specs)

def log_device_activity(device_id, action):
    """
    Enregistre l'activité du dispositif.
    """
    device = get_device(device_id)
    if device:
        device.last_active = timezone.now()
        device.save()
        
        # Logging de l'activité
        BoardingError.objects.create(
            error_type='activity_log',
            error_details={
                'device_id': device_id,
                'action': action,
                'timestamp': timezone.now().isoformat()
            }
        )
        return True
    return False

def check_device_connectivity(device_id):
    """
    Vérifie l'état de connexion du dispositif.
    """
    device = get_device(device_id)
    if device:
        return device.last_active >= timezone.now() - timezone.timedelta(minutes=5)
    return False

def register_device(device_info):
    """
    Enregistre un nouveau dispositif ou met à jour ses informations.
    """
    try:
        device_id = device_info.get('device_id')
        device_type = device_info.get('device_type')
        device_specs = device_info.get('device_specs')

        if not all([device_id, device_type, device_specs]):
            raise DeviceError("Informations de dispositif incomplètes")

        if not validate_device_specs(device_specs):
            raise DeviceError("Spécifications de dispositif invalides")

        device, created = BoardingDevice.objects.update_or_create(
            device_id=device_id,
            defaults={
                'device_type': device_type,
                'device_specs': device_specs,
                'status': 'active',
                'last_active': timezone.now()
            }
        )
        
        log_device_activity(device_id, 'register' if created else 'update')
        return device

    except Exception as e:
        raise DeviceError(f"Erreur lors de l'enregistrement du dispositif: {str(e)}")

def update_device_status(device_id, status):
    """
    Met à jour le statut du dispositif (par exemple, 'active', 'inactive', 'maintenance').
    """
    try:
        device = get_device(device_id)
        if device:
            device.status = status
            device.save()
            log_device_activity(device_id, f'status_update_{status}')
            return True
        return False
    except Exception as e:
        raise DeviceError(f"Erreur lors de la mise à jour du statut: {str(e)}")

def start_device_session(device_id, trip_id):
    """
    Démarre une nouvelle session pour un dispositif après s'être assuré qu'il n'y a qu'une seule session active.
    """
    try:
        ensure_single_active_session(device_id)
        device = get_device(device_id)
        
        if not device:
            raise DeviceError(f"Dispositif avec ID {device_id} introuvable.")
            
        if not check_device_connectivity(device_id):
            raise DeviceError("Le dispositif n'est pas connecté")

        session = BoardingSession.objects.create(
            device=device,
            trip_id=trip_id,
            status='active',
            start_time=timezone.now()
        )
        
        log_device_activity(device_id, 'session_start')
        return session

    except Exception as e:
        raise DeviceError(f"Erreur lors du démarrage de la session: {str(e)}")

def end_device_session(session_id):
    """
    Termine une session de dispositif en mettant à jour son statut.
    """
    try:
        with transaction.atomic():
            session = BoardingSession.objects.get(id=session_id)
            session.status = 'ended'
            session.end_time = timezone.now()
            session.save()
            
            log_device_activity(session.device.device_id, 'session_end')
            return True
            
    except BoardingSession.DoesNotExist:
        return False
    except Exception as e:
        raise DeviceError(f"Erreur lors de la terminaison de la session: {str(e)}")

def validate_device_context(device_id, driver_id, trip_id):
    """
    Valide que le dispositif, le chauffeur et le voyage sont correctement associés.
    """
    try:
        device = get_device(device_id)
        if not device:
            return False

        if not check_device_connectivity(device_id):
            return False

        # Vérifier si le chauffeur est assigné au voyage
        from transport_management.models import DriverVehicleAssignment

        assignment = DriverVehicleAssignment.objects.filter(
            driver_id=driver_id, 
            trip_id=trip_id, 
            status='active'
        ).exists()

        if assignment:
            log_device_activity(device_id, 'context_validation_success')
            return True
            
        log_device_activity(device_id, 'context_validation_failure')
        return False

    except Exception as e:
        raise DeviceError(f"Erreur lors de la validation du contexte: {str(e)}")