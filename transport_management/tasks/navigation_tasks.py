# transport_management/tasks/navigation_tasks.py

from celery import shared_task
from ..services.navigation.navigation_manager import NavigationManager

@shared_task
def update_navigation(trip_id):
    manager = NavigationManager()
    manager.process_navigation_update(trip_id)