# views/boarding/utils/sync_manager.py

import json
from django.utils import timezone
from membership_management.models import OfflineValidation, BoardingSession
from membership_management.views.boarding.boarding_utils.validations import validate_nfc_card, validate_qr_code
from membership_management.views.boarding.boarding_utils.validations import handle_validation_exception

def store_offline_validation(data):
    """
    Stocke les validations effectuées en mode hors-ligne dans la base de données pour une synchronisation ultérieure.
    """
    try:
        # Créer un enregistrement d'une validation hors-ligne
        OfflineValidation.objects.create(
            passenger_id=data.get('passenger_id'),
            trip_id=data.get('trip_id'),
            scan_type=data.get('scan_type'),  # 'nfc' ou 'qr'
            timestamp=timezone.now(),
            data=json.dumps(data),  # Stocker les données brutes pour référence
            status='pending'  # Statut indiquant que la validation doit être synchronisée
        )
        return True
    except Exception as e:
        print(f"Erreur lors du stockage de la validation hors-ligne : {e}")
        handle_validation_exception(e)
        return False

def process_sync_queue():
    """
    Traite la file de synchronisation lors de la reconnexion.
    """
    try:
        # Récupérer les validations hors-ligne en attente
        pending_validations = OfflineValidation.objects.filter(status='pending')
        for validation in pending_validations:
            try:
                # Traiter chaque validation comme s'il s'agissait d'une validation en ligne
                if validation.scan_type == 'nfc':
                    card_data = json.loads(validation.data)
                    result = validate_nfc_card(card_data)
                elif validation.scan_type == 'qr':
                    qr_data = json.loads(validation.data)
                    result = validate_qr_code(qr_data)
                else:
                    result = {"status": "failure", "message": "Type de scan inconnu."}

                if result['status'] == 'success':
                    # Marquer la validation comme synchronisée
                    validation.status = 'synced'
                    validation.synchronized_at = timezone.now()
                    validation.save()
                else:
                    # Gérer les échecs de synchronisation
                    validation.status = 'failed'
                    validation.save()
            except Exception as e:
                print(f"Erreur lors de la synchronisation de la validation ID {validation.id}: {e}")
                validation.status = 'failed'
                validation.save()
    except Exception as e:
        print(f"Erreur générale lors du traitement de la queue de synchronisation : {e}")
        handle_validation_exception(e)

def resolve_conflicts(local_data, server_data):
    """
    Résout les conflits entre les données locales et celles du serveur.
    """
    # Implémentation de votre logique de résolution des conflits
    # Exemple :
    # - Priorité aux données du serveur
    # - Ou fusion des données en fonction de l'horodatage
    pass

def update_sync_status(session_id, status):
    """
    Met à jour le statut de synchronisation d'une session.
    """
    try:
        session = BoardingSession.objects.get(id=session_id)
        session.sync_status = status
        session.save()
        return True
    except BoardingSession.DoesNotExist:
        print(f"Session ID {session_id} introuvable lors de la mise à jour du statut de synchronisation.")
        return False
    except Exception as e:
        print(f"Erreur lors de la mise à jour du statut de synchronisation pour la session ID {session_id} : {e}")
        handle_validation_exception(e)
        return False
