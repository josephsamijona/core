# transport_api/signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Schedule, ScheduleException
from django.utils import timezone

@receiver(post_save, sender=Schedule)
def schedule_updated(sender, instance, created, **kwargs):
    today = timezone.now().date()
    if instance.start_date <= today <= instance.end_date and instance.is_active:
        instance.generate_timepoints_for_date(today)

@receiver(post_delete, sender=Schedule)
def schedule_deleted(sender, instance, **kwargs):
    # Supprimer les horaires associés si nécessaire
    pass

@receiver(post_save, sender=ScheduleException)
def schedule_exception_updated(sender, instance, created, **kwargs):
    instance.schedule.generate_timepoints_for_date(instance.exception_date)
