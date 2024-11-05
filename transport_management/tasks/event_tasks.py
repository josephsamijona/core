# transport_management/tasks/event_tasks.py

from celery import shared_task
from ..services.event.event_manager import TripEventManager

@shared_task
def process_trip_events(trip_id):
    """
    Tâche périodique pour détecter les événements
    Doit s'exécuter fréquemment (par exemple toutes les 30 secondes)
    """
    manager = TripEventManager()
    manager.process_events(trip_id)