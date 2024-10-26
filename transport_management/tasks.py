# transport_api/tasks.py

from celery import shared_task
from .models import Schedule
from django.utils import timezone

@shared_task
def generate_daily_schedules():
    today = timezone.now().date()
    schedules = Schedule.objects.filter(
        start_date__lte=today,
        end_date__gte=today,
        day_of_week=today.strftime('%A').lower(),
        is_active=True,
    )
    for schedule in schedules:
        schedule.generate_timepoints_for_date(today)
