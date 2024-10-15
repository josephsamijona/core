from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from user_management.models import Notification, User
from membership_management.models import Subscription, TransportCard, Payment
from transport_management.models import Reservation, Trip, Vehicle
from user_management.notification_service import NotificationService

@receiver(pre_save, sender=Subscription)
def check_subscription_expiration(sender, instance, **kwargs):
    if instance.end_date - timezone.now().date() <= timezone.timedelta(days=7):
        NotificationService.subscription_expiring_notification(instance)

@receiver(post_save, sender=Subscription)
def notify_subscription_changes(sender, instance, created, **kwargs):
    if created:
        NotificationService.create_notification(
            user=instance.passenger.user,
            notification_type='subscription_created',
            message=f"Votre nouvel abonnement est actif jusqu'au {instance.end_date}.",
            priority='medium'
        )
    elif instance.auto_renew:
        NotificationService.auto_renewal_notification(instance)

@receiver(post_save, sender=Trip)
def notify_trip_changes(sender, instance, created, **kwargs):
    if created:
        NotificationService.trip_notification(instance, 'trip_reminder')
    else:
        # Vérifier si le voyage a été retardé ou annulé
        if instance.is_delayed():
            NotificationService.trip_notification(instance, 'trip_delay')
        elif instance.is_cancelled():
            NotificationService.trip_notification(instance, 'trip_cancellation')

@receiver(pre_save, sender=TransportCard)
def check_card_expiration(sender, instance, **kwargs):
    if instance.expiry_date - timezone.now().date() <= timezone.timedelta(days=30):
        NotificationService.card_notification(instance, 'card_expiring')

@receiver(post_save, sender=TransportCard)
def notify_card_status_changes(sender, instance, created, **kwargs):
    if instance.is_blocked():
        NotificationService.card_notification(instance, 'card_blocked')
    elif instance.is_replaced():
        NotificationService.card_notification(instance, 'card_replaced')

@receiver(post_save, sender=Payment)
def notify_payment_status(sender, instance, created, **kwargs):
    if created:
        if instance.status == 'success':
            NotificationService.payment_notification(instance, 'success')
        elif instance.status == 'failed':
            NotificationService.payment_notification(instance, 'failed')
    elif instance.status == 'due':
        NotificationService.payment_notification(instance, 'due')

@receiver(post_save, sender=User)
def notify_account_changes(sender, instance, **kwargs):
    # Vérifier si le mot de passe a été modifié
    if instance._state.adding or 'password' in instance.get_deferred_fields():
        # Envoi d'une notification à l'utilisateur
        instance.email_user(
            subject="Changement de mot de passe",
            message="Votre mot de passe a été modifié avec succès. Si ce n'était pas vous, contactez immédiatement le support."
        )
@receiver(post_save, sender=Reservation)
def notify_reservation_status(sender, instance, created, **kwargs):
    if created:
        NotificationService.reservation_notification(instance, 'reservation_confirmation')
    else:
        if instance.status == 'confirmed':
            NotificationService.reservation_notification(instance, 'reservation_reminder')
        elif instance.status == 'cancelled':
            NotificationService.reservation_notification(instance, 'reservation_change')

# Vous pouvez ajouter d'autres signaux ici pour d'autres modèles ou événements

def notify_service_disruption(route, message):
    affected_users = User.objects.filter(subscriptions__route=route)
    NotificationService.service_disruption_notification(route, affected_users)

def notify_price_change(subscription_plan):
    NotificationService.price_change_notification(subscription_plan)

def notify_new_feature(feature_name, affected_users):
    NotificationService.new_feature_notification(feature_name, affected_users)

def notify_maintenance_alert(maintenance_info, affected_users):
    NotificationService.maintenance_alert_notification(maintenance_info, affected_users)

def notify_suspicious_activity(user, activity_details):
    NotificationService.suspicious_activity_notification(user, activity_details)

def notify_login_from_new_device(user, device_info):
    NotificationService.login_from_new_device_notification(user, device_info)
    
    
