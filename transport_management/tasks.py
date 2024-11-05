# schedule/tasks.py

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from .models import Schedule, Trip, DisplaySchedule
from celery.utils.log import get_task_logger
from datetime import datetime, timedelta
from django.contrib.auth.models import User

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3)
def generate_daily_schedules(self):
    """
    Génère les trips et display schedules quotidiens avec gestion des erreurs et verrouillage.
    """
    today = timezone.localdate()
    logger.info(f"Début de la génération des trips pour {today}")
    
    try:
        with transaction.atomic():
            # Récupérer les schedules actifs pour aujourd'hui
            schedules = Schedule.objects.select_for_update().filter(
                start_date__lte=today,
                end_date__gte=today,
                day_of_week=today.strftime('%A').lower(),
                status='active',
                is_current_version=True,
                is_active=True,
            )

            for schedule in schedules:
                try:
                    # Vérifier si des trips existent déjà pour ce schedule et cette date
                    existing_trips = Trip.objects.filter(schedule=schedule, trip_date=today)
                    if existing_trips.exists():
                        logger.info(f"Les trips pour l'horaire {schedule.id} existent déjà pour {today}")
                        continue  # Passer au prochain schedule

                    # Générer les trips pour la date du jour
                    trips = schedule.generate_trips_for_date(today)
                    logger.info(f"{len(trips)} trips générés pour l'horaire {schedule.id} pour la date {today}")

                    # Générer les DisplaySchedules associés
                    for trip in trips:
                        # Récupérer ou définir les valeurs nécessaires
                        bus_number = trip.vehicle.license_plate if trip.vehicle else 'N/A'
                        gate_number = trip.gate_number if hasattr(trip, 'gate_number') else 'G1'  # Ajustez si nécessaire
                        modified_by = trip.modified_by if trip.modified_by else User.objects.first()  # Utilisateur par défaut
                        notes = trip.notes if hasattr(trip, 'notes') else ''
                        display_order = trip.display_order if hasattr(trip, 'display_order') else 0

                        DisplaySchedule.objects.create(
                            trip=trip,
                            bus_number=bus_number,
                            scheduled_departure=trip.planned_departure,
                            scheduled_arrival=trip.planned_arrival,
                            gate_number=gate_number,
                            status=trip.status,
                            display_order=display_order,
                            modified_by=modified_by,
                            notes=notes,
                        )
                    logger.info(f"{len(trips)} DisplaySchedules créés pour l'horaire {schedule.id} pour la date {today}")

                except Exception as e:
                    logger.error(f"Erreur lors de la génération pour l'horaire {schedule.id}: {str(e)}")

        logger.info(f"Génération des trips et display schedules terminée pour {today}")
        return f"Génération des trips et display schedules terminée pour {today}"
        
    except Exception as exc:
        logger.error(f"Erreur lors de la génération des trips: {str(exc)}")
        self.retry(exc=exc, countdown=60)  # Réessayer dans 1 minute

        self.retry(exc=exc, countdown=60)  # Réessayer dans 1 minute


@shared_task
def cleanup_old_schedules():
    """
    Archive les anciens horaires.
    """
    today = timezone.now().date()
    with transaction.atomic():
        old_schedules = Schedule.objects.filter(
            end_date__lt=today,
            status__in=['active', 'validated'],
            is_active=True
        )
        for schedule in old_schedules:
            schedule.archive()
            logger.info(f"Horaire {schedule.id} archivé")

@shared_task
def activate_pending_schedules():
    """
    Active les horaires validés qui doivent démarrer aujourd'hui.
    """
    today = timezone.now().date()
    with transaction.atomic():
        pending_schedules = Schedule.objects.filter(
            start_date=today,
            status='validated',
            is_approved=True,
            is_active=True
        )
        for schedule in pending_schedules:
            schedule.activate()
            logger.info(f"Horaire {schedule.id} activé")

@shared_task
def update_trip_statuses():
    """Mise à jour des statuts pour tous les trips actifs."""
    active_trips = Trip.objects.filter(
        planned_arrival__gte=timezone.now(),
        status__in=['scheduled', 'boarding_soon', 'boarding', 'in_transit', 'arriving_soon']
    )
    for trip in active_trips:
        trip.update_status()
        
        
