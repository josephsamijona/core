# transport_management/tasks/trip_lifecycle_tasks.py

from celery import shared_task
from ..services.trip_lifecycle.lifecycle_manager import TripLifecycleManager

@shared_task
def update_trip_lifecycles():
    """Tâche périodique pour mettre à jour les trips"""
    manager = TripLifecycleManager()
    manager.process_lifecycle_updates()
    
