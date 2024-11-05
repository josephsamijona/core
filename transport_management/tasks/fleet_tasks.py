# transport_management/tasks/fleet_tasks.py

from celery import shared_task
from ..services.resource.fleet_manager import FleetManager

@shared_task
def monitor_fleet():
    """
    Tâche périodique pour la surveillance de la flotte
    À exécuter toutes les minutes
    """
    manager = FleetManager()
    manager.monitor_active_fleet()