# transport_management/tasks/scheduler_tasks.py

from celery import shared_task
from django.utils import timezone
from ..services.trip_scheduler.trip_generator import TripGeneratorService

@shared_task
def generate_daily_trips():
    """Tâche Celery pour générer les trips quotidiens"""
    service = TripGeneratorService()
    return service.generate_daily_trips()

@shared_task
def check_and_prepare_next_day_trips():
    """Tâche Celery pour préparer les trips du lendemain"""
    tomorrow = timezone.now().date() + timezone.timedelta(days=1)
    service = TripGeneratorService()
    return service.generate_daily_trips(tomorrow)