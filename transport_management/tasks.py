# transport_api/tasks.py
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from .models import Schedule
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3)
def generate_daily_schedules(self):
    """
    Génère les horaires quotidiens avec gestion des erreurs et verrouillage.
    """
    today = timezone.now().date()
    logger.info(f"Début de la génération des horaires pour {today}")
    
    try:
        with transaction.atomic():
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
                    schedule.generate_timepoints_for_date(today)
                    logger.info(f"Horaire {schedule.id} généré avec succès")
                except Exception as e:
                    logger.error(f"Erreur lors de la génération de l'horaire {schedule.id}: {str(e)}")

        return f"Génération des horaires terminée pour {today}"
        
    except Exception as exc:
        logger.error(f"Erreur lors de la génération des horaires: {str(exc)}")
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

