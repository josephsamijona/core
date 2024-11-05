# transport_management/tasks/reporting_tasks.py

from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from ..services.reporting.reporting_service import ReportingService

@shared_task
def generate_daily_reports():
    """Génère les rapports quotidiens"""
    service = ReportingService()
    yesterday = timezone.now().date() - timedelta(days=1)
    return service.generate_trip_analysis(date_from=yesterday, date_to=yesterday)

@shared_task
def generate_trip_report(trip_id):
    """Génère un rapport pour un trip spécifique"""
    service = ReportingService()
    return service.generate_trip_analysis(trip_id=trip_id)
