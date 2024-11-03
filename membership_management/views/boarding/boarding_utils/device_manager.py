# views/boarding/utils/device_manager.py

from membership_management.models import BoardingDevice, BoardingSession
from django.utils import timezone
from django.db import transaction

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

def register_device(device_info):
    """
    Enregistre un nouveau dispositif ou met à jour ses informations.
    """
    device_id = device_info.get('device_id')
    device_type = device_info.get('device_type')
    device_specs = device_info.get('device_specs')

    device, created = BoardingDevice.objects.update_or_create(
        device_id=device_id,
        defaults={
            'device_type': device_type,
            'device_specs': device_specs,
            'status': 'active'
        }
    )
    return device

def update_device_status(device_id, status):
    """
    Met à jour le statut du dispositif (par exemple, 'active', 'inactive', 'maintenance').
    """
    device = get_device(device_id)
    if device:
        device.status = status
        device.save()
        return True
    return False

def start_device_session(device_id, trip_id):
    """
    Démarre une nouvelle session pour un dispositif après s'être assuré qu'il n'y a qu'une seule session active.
    """
    ensure_single_active_session(device_id)
    device = get_device(device_id)
    if not device:
        raise Exception(f"Dispositif avec ID {device_id} introuvable.")

    session = BoardingSession.objects.create(
        device=device,
        trip_id=trip_id,
        status='active',
        start_time=timezone.now()
    )
    return session

def end_device_session(session_id):
    """
    Termine une session de dispositif en mettant à jour son statut.
    """
    try:
        session = BoardingSession.objects.get(id=session_id)
        session.status = 'ended'
        session.end_time = timezone.now()
        session.save()
        return True
    except BoardingSession.DoesNotExist:
        return False

def validate_device_context(device_id, driver_id, trip_id):
    """
    Valide que le dispositif, le chauffeur et le voyage sont correctement associés.
    """
    # Implémentation selon votre logique métier
    # Par exemple, vérifier si le dispositif est assigné au chauffeur et au voyage
    device = get_device(device_id)
    if not device:
        return False

    # Vérifier si le chauffeur est assigné au voyage
    # Supposons que vous avez un modèle DriverAssignment
    from transport_management.models import DriverVehicleAssignment

    try:
        assignment = DriverVehicleAssignment.objects.get(driver_id=driver_id, trip_id=trip_id, status='active')
        return True
    except DriverVehicleAssignment.DoesNotExist:
        return False
