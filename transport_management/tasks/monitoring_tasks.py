# transport_management/tasks/monitoring_tasks.py

from celery import shared_task
from ..services.monitoring.trip_monitor import TripMonitoringService

@shared_task
def monitor_active_trips():
    service = TripMonitoringService()
    service.monitor_active_trips()