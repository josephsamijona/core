# transport_management/tasks/emergency_tasks.py

from celery import shared_task
from ..services.emergency.emergency_manager import EmergencyManager

@shared_task
def check_emergency_situations():
    """
    Tâche périodique pour vérifier les situations d'urgence
    À exécuter toutes les 60 secondes
    """
    manager = EmergencyManager()
    manager.check_emergencies()

@shared_task
def check_specific_trip_emergency(trip_id):
    """
    Vérifie les situations d'urgence pour un trip spécifique
    """
    manager = EmergencyManager()
    manager.check_emergencies(trip_id)