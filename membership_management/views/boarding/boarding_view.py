# views/boarding/boarding_views.py

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
import json

from membership_management.views.boarding.boarding_utils.device_manager import (
    register_device,
    get_device,
    update_device_status,
    start_device_session,
    end_device_session,
    validate_device_context
)
from membership_management.views.boarding.boarding_utils.validations import (
    validate_nfc_card,
    validate_qr_code,
    is_duplicate_scan,
    log_validation_error
)
from membership_management.views.boarding.boarding_utils.sync_manager import (
    store_local_validation,
    enqueue_unsynced_data,
    process_sync_queue,
    resolve_conflicts,
    update_sync_status
)
from transport_management.models import Trip,TransactionScan,Incident
from membership_management.models import (
    BoardingSession,
    TransactionScan,
    BoardingValidation,
    OfflineValidation,
    BoardingError,
    
)

# ------------------------------
# Vues Principales de Boarding
# ------------------------------

@csrf_exempt
def initialize_boarding(request):
    """
    Démarre une nouvelle session de boarding.
    Attendu:
    {
        "device_id": "DEVICE123",
        "trip_id": "TRIP123",
        "driver_id": "DRIVER456"
    }
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            device_id = data.get('device_id')
            trip_id = data.get('trip_id')
            driver_id = data.get('driver_id')

            if not device_id or not trip_id or not driver_id:
                return JsonResponse({"status": "failure", "message": "Données manquantes."}, status=400)

            # Valider le contexte du dispositif, du chauffeur et du voyage
            if not validate_device_context(device_id, driver_id, trip_id):
                return JsonResponse({"status": "failure", "message": "Contexte invalide."}, status=400)

            # Démarrer une nouvelle session de boarding
            session = start_device_session(device_id, trip_id)

            return JsonResponse({
                "status": "success",
                "session_id": session.id,
                "message": "Session de boarding initialisée."
            }, status=201)
        except json.JSONDecodeError:
            return JsonResponse({"status": "failure", "message": "JSON non valide."}, status=400)
        except Exception as e:
            log_validation_error({"error_message": str(e)})
            return JsonResponse({"status": "failure", "message": "Erreur lors de l'initialisation de la session."}, status=500)
    else:
        return JsonResponse({"status": "failure", "message": "Méthode non autorisée."}, status=405)


@csrf_exempt
def end_boarding_session(request, session_id):
    """
    Termine une session de boarding active.
    """
    if request.method == 'POST':
        try:
            success = end_device_session(session_id)
            if success:
                return JsonResponse({"status": "success", "message": "Session terminée."}, status=200)
            else:
                return JsonResponse({"status": "failure", "message": "Session introuvable."}, status=404)
        except Exception as e:
            log_validation_error({"error_message": str(e)})
            return JsonResponse({"status": "failure", "message": "Erreur lors de la terminaison de la session."}, status=500)
    else:
        return JsonResponse({"status": "failure", "message": "Méthode non autorisée."}, status=405)


def get_boarding_status(request, session_id):
    """
    Récupère le statut actuel d'une session de boarding.
    Fournit des informations telles que le nombre de passagers embarqués.
    """
    try:
        session = BoardingSession.objects.get(id=session_id)
        trip = session.trip

        data = {
            "session_id": session.id,
            "status": session.status,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "trip_id": trip.id,
            "destination": trip.destination,
            "current_passenger_count": trip.current_passenger_count,
            "capacity": trip.capacity
        }

        return JsonResponse({"status": "success", "data": data}, status=200)
    except BoardingSession.DoesNotExist:
        return JsonResponse({"status": "failure", "message": "Session introuvable."}, status=404)
    except Exception as e:
        log_validation_error({"error_message": str(e)})
        return JsonResponse({"status": "failure", "message": "Erreur lors de la récupération du statut."}, status=500)


# ------------------------------
# Gestion des Passagers
# ------------------------------

@csrf_exempt
def process_boarding(request):
    """
    Traite une validation de boarding.
    Attendu:
    {
        "passenger_id": "PASSENGER123",
        "trip_id": "TRIP123",
        "scan_type": "nfc" ou "qr"
    }
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            passenger_id = data.get('passenger_id')
            trip_id = data.get('trip_id')
            scan_type = data.get('scan_type')  # 'nfc' ou 'qr'

            if not passenger_id or not trip_id or not scan_type:
                return JsonResponse({"status": "failure", "message": "Données manquantes."}, status=400)

            # Vérifier si le scan est en double
            scan_time = timezone.now()
            if is_duplicate_scan(passenger_id, trip_id, scan_time):
                return JsonResponse({"status": "failure", "message": "Scan en double détecté."}, status=400)

            # Valider le scan
            if scan_type == 'nfc':
                validation_result = validate_nfc_card(data)
            elif scan_type == 'qr':
                validation_result = validate_qr_code(data)
            else:
                return JsonResponse({"status": "failure", "message": "Type de scan invalide."}, status=400)

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
                return JsonResponse({"status": "failure", "message": validation_result['message']}, status=400)
        except Exception as e:
            log_validation_error({"error_message": str(e)})
            return JsonResponse({"status": "failure", "message": "Erreur lors du traitement du boarding."}, status=500)
    else:
        return JsonResponse({"status": "failure", "message": "Méthode non autorisée."}, status=405)


@csrf_exempt
def cancel_boarding(request, passenger_trip_id):
    """
    Annule une validation de boarding pour un passager.
    Attendu:
    {
        "message": "Raison de l'annulation (optionnel)"
    }
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', 'Annulation par le passager.')

            # Trouver l'enregistrement BoardingValidation
            validation = BoardingValidation.objects.get(id=passenger_trip_id)

            if validation.status != 'successful':
                return JsonResponse({"status": "failure", "message": "Validation déjà annulée ou non réussie."}, status=400)

            # Mettre à jour le statut de la validation
            validation.status = 'cancelled'
            validation.save()

            # Mettre à jour le compteur de passagers du trip
            trip = validation.trip
            if trip.current_passenger_count > 0:
                trip.current_passenger_count -= 1
                trip.save()

            return JsonResponse({"status": "success", "message": "Validation annulée avec succès."}, status=200)
        except BoardingValidation.DoesNotExist:
            return JsonResponse({"status": "failure", "message": "Validation introuvable."}, status=404)
        except Exception as e:
            log_validation_error({"error_message": str(e)})
            return JsonResponse({"status": "failure", "message": "Erreur lors de l'annulation du boarding."}, status=500)
    else:
        return JsonResponse({"status": "failure", "message": "Méthode non autorisée."}, status=405)


@csrf_exempt
def update_passenger_count(request, trip_id):
    """
    Met à jour ou récupère le nombre de passagers pour un voyage donné.
    """
    if request.method == 'GET':
        try:
            trip = Trip.objects.get(id=trip_id)
            data = {
                "trip_id": trip.id,
                "destination": trip.destination,
                "current_passenger_count": trip.current_passenger_count,
                "capacity": trip.capacity
            }
            return JsonResponse({"status": "success", "data": data}, status=200)
        except Trip.DoesNotExist:
            return JsonResponse({"status": "failure", "message": "Voyage introuvable."}, status=404)
        except Exception as e:
            log_validation_error({"error_message": str(e)})
            return JsonResponse({"status": "failure", "message": "Erreur lors de la récupération du nombre de passagers."}, status=500)
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_count = data.get('new_count')

            if new_count is None or not isinstance(new_count, int):
                return JsonResponse({"status": "failure", "message": "Nouveau nombre de passagers invalide."}, status=400)

            trip = Trip.objects.get(id=trip_id)
            trip.current_passenger_count = new_count
            trip.save()

            return JsonResponse({"status": "success", "message": "Nombre de passagers mis à jour.", "current_passenger_count": new_count}, status=200)
        except Trip.DoesNotExist:
            return JsonResponse({"status": "failure", "message": "Voyage introuvable."}, status=404)
        except Exception as e:
            log_validation_error({"error_message": str(e)})
            return JsonResponse({"status": "failure", "message": "Erreur lors de la mise à jour du nombre de passagers."}, status=500)
    else:
        return JsonResponse({"status": "failure", "message": "Méthode non autorisée."}, status=405)


# ------------------------------
# Monitoring
# ------------------------------

def get_boarding_statistics(request, session_id):
    """
    Fournit des statistiques en temps réel sur les embarquements.
    Inclut le nombre total de passagers, les anomalies détectées, etc.
    """
    try:
        session = BoardingSession.objects.get(id=session_id)
        trip = session.trip

        total_passengers = trip.current_passenger_count
        capacity = trip.capacity
        anomalies = BoardingValidation.objects.filter(trip=trip, status='failed').count()

        data = {
            "session_id": session.id,
            "trip_id": trip.id,
            "destination": trip.destination,
            "total_passengers": total_passengers,
            "capacity": capacity,
            "anomalies_detected": anomalies
        }

        return JsonResponse({"status": "success", "data": data}, status=200)
    except BoardingSession.DoesNotExist:
        return JsonResponse({"status": "failure", "message": "Session introuvable."}, status=404)
    except Exception as e:
        log_validation_error({"error_message": str(e)})
        return JsonResponse({"status": "failure", "message": "Erreur lors de la récupération des statistiques."}, status=500)


def get_recent_boardings(request, session_id):
    """
    Récupère les dernières validations de boarding.
    """
    try:
        session = BoardingSession.objects.get(id=session_id)
        trip = session.trip

        recent_boardings = BoardingValidation.objects.filter(trip=trip).order_by('-timestamp')[:20]
        boardings_data = [
            {
                "passenger_id": validation.passenger.id,
                "scan_type": validation.scan_type,
                "timestamp": validation.timestamp,
                "status": validation.status
            }
            for validation in recent_boardings
        ]

        return JsonResponse({"status": "success", "data": boardings_data}, status=200)
    except BoardingSession.DoesNotExist:
        return JsonResponse({"status": "failure", "message": "Session introuvable."}, status=404)
    except Exception as e:
        log_validation_error({"error_message": str(e)})
        return JsonResponse({"status": "failure", "message": "Erreur lors de la récupération des récents embarquements."}, status=500)


def get_boarding_alerts(request, session_id):
    """
    Récupère les alertes et notifications associées à la session.
    """
    try:
        session = BoardingSession.objects.get(id=session_id)
        trip = session.trip

        # Exemple d'alertes : Anomalies, incidents, etc.
        anomalies = BoardingValidation.objects.filter(trip=trip, status='failed')
        incidents = Incident.objects.filter(trip=trip)

        alerts = []

        for anomaly in anomalies:
            alerts.append({
                "type": "anomaly",
                "message": f"Échec de validation pour le passager {anomaly.passenger.id}.",
                "timestamp": anomaly.timestamp
            })

        for incident in incidents:
            alerts.append({
                "type": "incident",
                "message": f"Incident rapporté : {incident.description}",
                "timestamp": incident.reported_at
            })

        # Trier les alertes par timestamp décroissant
        alerts_sorted = sorted(alerts, key=lambda x: x['timestamp'], reverse=True)

        return JsonResponse({"status": "success", "data": alerts_sorted}, status=200)
    except BoardingSession.DoesNotExist:
        return JsonResponse({"status": "failure", "message": "Session introuvable."}, status=404)
    except Exception as e:
        log_validation_error({"error_message": str(e)})
        return JsonResponse({"status": "failure", "message": "Erreur lors de la récupération des alertes."}, status=500)
