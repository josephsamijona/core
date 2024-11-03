# views/boarding/validation_views.py

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json

from membership_management.views.boarding.boarding_utils.validations import (
    validate_nfc_card,
    validate_qr_code,
    is_duplicate_scan,
    log_validation_error
)
from membership_management.views.boarding.boarding_utils.sync_manager import (
    enqueue_unsynced_data
)
from membership_management.models import (
    BoardingError,
    BoardingValidation,
    PassengerUser,
    
)
from transport_management.models import Trip,TransactionScan,Incident
@csrf_exempt
def validate_nfc_card_view(request):
    """
    Valide une carte NFC.
    Attendu:
    {
        "passenger_id": "PASSENGER123",
        "trip_id": "TRIP123",
        "scan_type": "nfc"
    }
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            passenger_id = data.get('passenger_id')
            trip_id = data.get('trip_id')
            scan_type = data.get('scan_type')

            if not passenger_id or not trip_id or scan_type != 'nfc':
                return JsonResponse({"status": "failure", "message": "Données manquantes ou type de scan invalide."}, status=400)

            # Vérifier si le scan est en double
            scan_time = timezone.now()
            if is_duplicate_scan(passenger_id, trip_id, scan_time):
                return JsonResponse({"status": "failure", "message": "Scan en double détecté."}, status=400)

            # Valider la carte NFC
            validation_result = validate_nfc_card(data)

            if validation_result['status'] == 'success':
                # Créer un enregistrement TransactionScan
                TransactionScan.objects.create(
                    passenger_id=passenger_id,
                    trip_id=trip_id,
                    scan_type=scan_type,
                    timestamp=scan_time,
                    status='successful'
                )

                # Mettre à jour le compteur de passagers du trip
                trip = Trip.objects.get(id=trip_id)
                trip.current_passenger_count += 1
                trip.save()

                # Créer un enregistrement BoardingValidation
                BoardingValidation.objects.create(
                    passenger_id=passenger_id,
                    trip_id=trip_id,
                    scan_type=scan_type,
                    timestamp=scan_time,
                    status='successful'
                )

                return JsonResponse({"status": "success", "message": "Validation réussie. Vous pouvez embarquer."}, status=200)
            else:
                # Enregistrer l'échec de validation
                BoardingValidation.objects.create(
                    passenger_id=passenger_id,
                    trip_id=trip_id,
                    scan_type=scan_type,
                    timestamp=scan_time,
                    status='failed'
                )

                # En mode hors-ligne, ajouter à la file de synchronisation
                if not request.is_ajax() and not request.META.get('HTTP_CONNECTION'):
                    enqueue_unsynced_data(data)

                return JsonResponse({"status": "failure", "message": validation_result['message']}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"status": "failure", "message": "JSON non valide."}, status=400)
        except PassengerUser.DoesNotExist:
            return JsonResponse({"status": "failure", "message": "Passager introuvable."}, status=404)
        except Trip.DoesNotExist:
            return JsonResponse({"status": "failure", "message": "Voyage introuvable."}, status=404)
        except Exception as e:
            log_validation_error({"error_message": str(e)})
            return JsonResponse({"status": "failure", "message": "Erreur lors de la validation de la carte NFC."}, status=500)
    else:
        return JsonResponse({"status": "failure", "message": "Méthode non autorisée."}, status=405)


@csrf_exempt
def validate_qr_code_view(request):
    """
    Valide un QR Code.
    Attendu:
    {
        "passenger_id": "PASSENGER123",
        "trip_id": "TRIP123",
        "scan_type": "qr",
        "qr_data": "base64_encoded_string"  # Optionnel si déjà décodé
    }
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            passenger_id = data.get('passenger_id')
            trip_id = data.get('trip_id')
            scan_type = data.get('scan_type')
            qr_data = data.get('qr_data')  # Optionnel

            if not passenger_id or not trip_id or scan_type != 'qr':
                return JsonResponse({"status": "failure", "message": "Données manquantes ou type de scan invalide."}, status=400)

            # Vérifier si le scan est en double
            scan_time = timezone.now()
            if is_duplicate_scan(passenger_id, trip_id, scan_time):
                return JsonResponse({"status": "failure", "message": "Scan en double détecté."}, status=400)

            # Si qr_data est fourni, décoder
            if qr_data:
                try:
                    qr_data_decoded = json.loads(qr_data)
                    data.update(qr_data_decoded)
                except json.JSONDecodeError:
                    return JsonResponse({"status": "failure", "message": "QR Code invalide (JSON non valide)."}, status=400)

            # Valider le QR Code
            validation_result = validate_qr_code(data)

            if validation_result['status'] == 'success':
                # Créer un enregistrement TransactionScan
                TransactionScan.objects.create(
                    passenger_id=passenger_id,
                    trip_id=trip_id,
                    scan_type=scan_type,
                    timestamp=scan_time,
                    status='successful'
                )

                # Mettre à jour le compteur de passagers du trip
                trip = Trip.objects.get(id=trip_id)
                trip.current_passenger_count += 1
                trip.save()

                # Créer un enregistrement BoardingValidation
                BoardingValidation.objects.create(
                    passenger_id=passenger_id,
                    trip_id=trip_id,
                    scan_type=scan_type,
                    timestamp=scan_time,
                    status='successful'
                )

                return JsonResponse({"status": "success", "message": "Validation réussie. Vous pouvez embarquer."}, status=200)
            else:
                # Enregistrer l'échec de validation
                BoardingValidation.objects.create(
                    passenger_id=passenger_id,
                    trip_id=trip_id,
                    scan_type=scan_type,
                    timestamp=scan_time,
                    status='failed'
                )

                # En mode hors-ligne, ajouter à la file de synchronisation
                if not request.is_ajax() and not request.META.get('HTTP_CONNECTION'):
                    enqueue_unsynced_data(data)

                return JsonResponse({"status": "failure", "message": validation_result['message']}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"status": "failure", "message": "JSON non valide."}, status=400)
        except PassengerUser.DoesNotExist:
            return JsonResponse({"status": "failure", "message": "Passager introuvable."}, status=404)
        except Trip.DoesNotExist:
            return JsonResponse({"status": "failure", "message": "Voyage introuvable."}, status=404)
        except Exception as e:
            log_validation_error({"error_message": str(e)})
            return JsonResponse({"status": "failure", "message": "Erreur lors de la validation du QR Code."}, status=500)
    else:
        return JsonResponse({"status": "failure", "message": "Méthode non autorisée."}, status=405)


def handle_validation_error_view(request):
    """
    Gère les erreurs de validation enregistrées.
    Peut être utilisé pour récupérer les erreurs ou effectuer des actions spécifiques.
    """
    if request.method == 'GET':
        try:
            errors = BoardingError.objects.all().order_by('-timestamp')[:20]  # Récupère les 20 dernières erreurs
            errors_data = [
                {
                    "error_message": error.error_message,
                    "additional_info": error.additional_info,
                    "timestamp": error.timestamp
                }
                for error in errors
            ]
            return JsonResponse({"status": "success", "data": errors_data}, status=200)
        except Exception as e:
            return JsonResponse({"status": "failure", "message": "Erreur lors de la récupération des erreurs."}, status=500)
    else:
        return JsonResponse({"status": "failure", "message": "Méthode non autorisée."}, status=405)
