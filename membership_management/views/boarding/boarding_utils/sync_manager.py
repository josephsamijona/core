import json
from django.utils import timezone
from django.db import transaction
from membership_management.models import (
    OfflineValidation, 
    BoardingSession,
    BoardingError
)
from membership_management.views.boarding.boarding_utils.validations import (
    validate_nfc_card, 
    validate_qr_code,
    handle_validation_exception
)

class SyncError(Exception):
    """Exception personnalisée pour les erreurs de synchronisation"""
    pass

def store_offline_validation(data):
    """
    Stocke les validations effectuées en mode hors-ligne dans la base de données.
    """
    try:
        with transaction.atomic():
            validation = OfflineValidation.objects.create(
                passenger_id=data.get('passenger_id'),
                trip_id=data.get('trip_id'),
                scan_type=data.get('scan_type'),  # 'nfc' ou 'qr'
                timestamp=timezone.now(),
                data=json.dumps(data),  # Stocker les données brutes
                status='pending'
            )
            
            # Logging de la validation hors-ligne
            log_sync_activity(validation.id, 'store', data)
            return True
    except Exception as e:
        error_message = f"Erreur stockage validation hors-ligne: {str(e)}"
        log_sync_error('store_error', error_message, data)
        handle_validation_exception(e)
        return False

def process_sync_queue(max_retries=3):
    """
    Traite la file de synchronisation lors de la reconnexion.
    
    Args:
        max_retries (int): Nombre maximum de tentatives de synchronisation
    """
    try:
        # Récupérer les validations en attente
        pending_validations = OfflineValidation.objects.filter(
            status='pending'
        ).order_by('timestamp')

        for validation in pending_validations:
            try:
                with transaction.atomic():
                    # Vérifier si c'est un doublon
                    if is_duplicate(validation):
                        validation.status = 'duplicate'
                        validation.save()
                        continue

                    # Traiter selon le type de validation
                    result = process_validation(validation)

                    if result['status'] == 'success':
                        validation.status = 'synced'
                        validation.synchronized_at = timezone.now()
                    else:
                        # Gestion des échecs
                        validation.retry_count = getattr(validation, 'retry_count', 0) + 1
                        if validation.retry_count >= max_retries:
                            validation.status = 'failed'
                        else:
                            validation.status = 'pending'

                    validation.save()
                    log_sync_activity(validation.id, 'process', result)

            except Exception as e:
                error_message = f"Erreur sync validation {validation.id}: {str(e)}"
                log_sync_error('process_error', error_message, {'validation_id': validation.id})
                validation.status = 'failed'
                validation.save()

    except Exception as e:
        error_message = f"Erreur traitement queue sync: {str(e)}"
        log_sync_error('queue_error', error_message)
        handle_validation_exception(e)

def process_validation(validation):
    """
    Traite une validation spécifique.
    
    Args:
        validation: Instance de OfflineValidation
    """
    try:
        data = json.loads(validation.data)
        if validation.scan_type == 'nfc':
            return validate_nfc_card(data)
        elif validation.scan_type == 'qr':
            return validate_qr_code(data)
        else:
            return {"status": "failure", "message": "Type de scan inconnu"}
    except Exception as e:
        raise SyncError(f"Erreur traitement validation: {str(e)}")

def is_duplicate(validation):
    """
    Vérifie si une validation est un doublon.
    
    Args:
        validation: Instance de OfflineValidation
    """
    try:
        data = json.loads(validation.data)
        time_threshold = validation.timestamp - timezone.timedelta(minutes=5)
        
        return OfflineValidation.objects.filter(
            passenger_id=data.get('passenger_id'),
            trip_id=data.get('trip_id'),
            status='synced',
            timestamp__gte=time_threshold
        ).exclude(id=validation.id).exists()
    except Exception as e:
        log_sync_error('duplicate_check_error', str(e), {'validation_id': validation.id})
        return False

def resolve_conflicts(local_data, server_data):
    """
    Résout les conflits entre les données locales et serveur.
    
    Args:
        local_data: Données locales
        server_data: Données du serveur
    """
    try:
        # Priorité au serveur par défaut
        resolved_data = server_data.copy()
        
        # Garder certaines données locales si plus récentes
        if local_data.get('timestamp', '') > server_data.get('timestamp', ''):
            resolved_data.update({
                'status': local_data.get('status'),
                'local_updates': local_data.get('local_updates', [])
            })
        
        log_sync_activity('conflict_resolution', 'resolve', {
            'local': local_data,
            'server': server_data,
            'resolved': resolved_data
        })
        
        return resolved_data
        
    except Exception as e:
        error_message = f"Erreur résolution conflit: {str(e)}"
        log_sync_error('resolve_error', error_message, {
            'local': local_data,
            'server': server_data
        })
        return server_data

def update_sync_status(session_id, status):
    """
    Met à jour le statut de synchronisation d'une session.
    
    Args:
        session_id: ID de la session
        status: Nouveau statut
    """
    try:
        with transaction.atomic():
            session = BoardingSession.objects.get(id=session_id)
            previous_status = session.sync_status
            session.sync_status = status
            session.save()
            
            log_sync_activity(session_id, 'status_update', {
                'previous': previous_status,
                'new': status
            })
            return True
            
    except BoardingSession.DoesNotExist:
        error_message = f"Session {session_id} introuvable"
        log_sync_error('session_error', error_message)
        return False
        
    except Exception as e:
        error_message = f"Erreur mise à jour statut sync session {session_id}: {str(e)}"
        log_sync_error('status_update_error', error_message)
        handle_validation_exception(e)
        return False

def log_sync_activity(reference_id, activity_type, details):
    """
    Enregistre une activité de synchronisation.
    
    Args:
        reference_id: ID de référence
        activity_type: Type d'activité
        details: Détails de l'activité
    """
    try:
        BoardingError.objects.create(
            error_type='sync_activity',
            error_details={
                'reference_id': reference_id,
                'activity_type': activity_type,
                'details': details,
                'timestamp': timezone.now().isoformat()
            }
        )
    except Exception as e:
        print(f"Erreur logging activité sync: {e}")

def log_sync_error(error_type, message, context=None):
    """
    Enregistre une erreur de synchronisation.
    
    Args:
        error_type: Type d'erreur
        message: Message d'erreur
        context: Contexte de l'erreur
    """
    try:
        BoardingError.objects.create(
            error_type='sync_error',
            error_details={
                'error_type': error_type,
                'message': message,
                'context': context,
                'timestamp': timezone.now().isoformat()
            }
        )
    except Exception as e:
        print(f"Erreur logging erreur sync: {e}")