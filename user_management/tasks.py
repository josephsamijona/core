from celery import shared_task
from django.utils import timezone
from transport_management.models import  Trip
from membership_management.models import Subscription
from .models import Notification
from .notification_service import NotificationService

@shared_task
def check_upcoming_trips():
    upcoming_trips = Trip.objects.filter(
        start_time__gte=timezone.now(),
        start_time__lte=timezone.now() + timezone.timedelta(hours=24)
    )
    for trip in upcoming_trips:
        for passenger in trip.passengers.all():
            NotificationService.create_notification(
                user=passenger,
                notification_type='trip_reminder',
                message=f"Rappel : Vous avez un voyage prévu demain à {trip.start_time.strftime('%H:%M')}",
                priority='high'
            )

@shared_task
def process_notifications():
    unprocessed_notifications = Notification.objects.filter(processed=False)
    for notification in unprocessed_notifications:
        NotificationService.send_notification(notification)
        notification.processed = True
        notification.save()