# transport_api/signals.py
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from .models import Schedule, ScheduleException
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

SCHEDULE_LOCK_TIMEOUT = 300  # 5 minutes

@receiver(pre_save, sender=Schedule)
def prevent_duplicate_active_versions(sender, instance, **kwargs):
    """
    Empêche d'avoir plusieurs versions actives du même horaire.
    """
    if instance.is_current_version and instance.status == 'active':
        Schedule.objects.filter(
            route=instance.route,
            day_of_week=instance.day_of_week,
            is_current_version=True
        ).exclude(pk=instance.pk).update(
            is_current_version=False,
            status='archived'
        )

@receiver(post_save, sender=Schedule)
def schedule_updated(sender, instance, created, **kwargs):
    """
    Gère les mises à jour d'horaires avec gestion de verrou.
    """
    lock_id = f"schedule_lock_{instance.id}"
    
    # Éviter les récursions infinies et les opérations en double
    if cache.get(lock_id):
        return

    try:
        cache.set(lock_id, True, SCHEDULE_LOCK_TIMEOUT)
        
        today = timezone.now().date()
        if (instance.start_date <= today <= instance.end_date and 
            instance.is_active and instance.status == 'active'):
            
            with transaction.atomic():
                instance.generate_timepoints_for_date(today)
                
                # Mettre à jour les exceptions si nécessaires
                ScheduleException.objects.filter(
                    schedule=instance,
                    exception_date=today
                ).update(processed=False)
                
    finally:
        cache.delete(lock_id)

@receiver(post_delete, sender=Schedule)
def schedule_deleted(sender, instance, **kwargs):
    """
    Gère la suppression d'horaires.
    """
    # Vérifier s'il y a d'autres versions à activer
    if instance.is_current_version:
        latest_version = (Schedule.objects
            .filter(
                route=instance.route,
                day_of_week=instance.day_of_week,
                status='validated'
            )
            .order_by('-schedule_version')
            .first()
        )
        if latest_version:
            latest_version.activate()

@receiver(post_save, sender=ScheduleException)
def schedule_exception_updated(sender, instance, created, **kwargs):
    """
    Gère les exceptions d'horaires.
    """
    lock_id = f"schedule_exception_lock_{instance.id}"
    
    if cache.get(lock_id):
        return

    try:
        cache.set(lock_id, True, SCHEDULE_LOCK_TIMEOUT)
        
        with transaction.atomic():
            instance.schedule.generate_timepoints_for_date(instance.exception_date)
            instance.processed = True
            instance.save(update_fields=['processed'])
            
    finally:
        cache.delete(lock_id)