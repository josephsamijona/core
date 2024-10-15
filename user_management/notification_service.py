from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import models
from .models import Notification, User
from membership_management.models import Subscription, TransportCard
from transport_management.models import Reservation, Trip, Vehicle

class NotificationService:
    @staticmethod
    def create_notification(user, notification_type, message, priority='medium', action_url=None, expiration_date=None, related_object=None):
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            message=message,
            priority=priority,
            action_url=action_url,
            expiration_date=expiration_date,
            related_object_id=related_object.id if related_object else None,
            related_object_type=related_object.__class__.__name__ if related_object else None
        )
        NotificationService.send_notification(notification)
        return notification

    @staticmethod
    def send_notification(notification):
        # Logique d'envoi basée sur le type de notification
        if notification.notification_type in ['subscription_expiring', 'subscription_expired', 'auto_renewal', 'payment_success', 'payment_failed', 'payment_due', 'price_change']:
            NotificationService.send_email_notification(notification)
        elif notification.notification_type in ['trip_reminder', 'trip_delay', 'trip_cancellation', 'service_disruption', 'route_change', 'maintenance_alert']:
            NotificationService.send_push_notification(notification)
        elif notification.notification_type in ['card_expiring', 'card_expired', 'card_blocked', 'card_replaced']:
            NotificationService.send_email_notification(notification)
            NotificationService.send_push_notification(notification)
        # Ajoutez d'autres conditions selon les types de notifications

    @staticmethod
    def send_email_notification(notification):
        subject = f"Notification: {notification.get_notification_type_display()}"
        send_mail(
            subject,
            notification.message,
            settings.DEFAULT_FROM_EMAIL,
            [notification.user.email],
            fail_silently=False,
        )

    @staticmethod
    def send_push_notification(notification):
        # Implémentez ici la logique pour envoyer une notification push
        pass

    @staticmethod
    def send_sms_notification(notification):
        # Implémentez ici la logique pour envoyer un SMS
        pass

    # Méthodes spécifiques pour chaque type de notification
    @staticmethod
    def subscription_expiring_notification(subscription):
        days_left = (subscription.end_date - timezone.now().date()).days
        message = f"Votre abonnement expire dans {days_left} jours. Pensez à le renouveler !"
        NotificationService.create_notification(
            user=subscription.passenger.user,
            notification_type='subscription_expiring',
            message=message,
            priority='high',
            action_url='/renew-subscription/',
            related_object=subscription
        )

    @staticmethod
    def subscription_expired_notification(subscription):
        message = f"Votre abonnement a expiré. Renouvelez-le pour continuer à bénéficier de nos services."
        NotificationService.create_notification(
            user=subscription.passenger.user,
            notification_type='subscription_expired',
            message=message,
            priority='high',
            action_url='/renew-subscription/',
            related_object=subscription
        )

    @staticmethod
    def auto_renewal_notification(subscription):
        message = f"Votre abonnement a été automatiquement renouvelé jusqu'au {subscription.end_date}."
        NotificationService.create_notification(
            user=subscription.passenger.user,
            notification_type='auto_renewal',
            message=message,
            priority='medium',
            related_object=subscription
        )

    @staticmethod
    def payment_notification(payment, status):
        if status == 'success':
            message = f"Votre paiement de {payment.amount} a été effectué avec succès."
            notification_type = 'payment_success'
        elif status == 'failed':
            message = f"Votre paiement de {payment.amount} a échoué. Veuillez réessayer."
            notification_type = 'payment_failed'
        else:
            message = f"Un paiement de {payment.amount} est dû pour votre abonnement."
            notification_type = 'payment_due'

        NotificationService.create_notification(
            user=payment.user,
            notification_type=notification_type,
            message=message,
            priority='high',
            action_url='/payment-details/',
            related_object=payment
        )

    @staticmethod
    def price_change_notification(subscription_plan):
        message = f"Le tarif de votre plan d'abonnement a changé. Nouveau prix : {subscription_plan.price}"
        for subscription in subscription_plan.subscriptions.all():
            NotificationService.create_notification(
                user=subscription.passenger.user,
                notification_type='price_change',
                message=message,
                priority='medium',
                action_url='/subscription-details/',
                related_object=subscription
            )

    @staticmethod
    def trip_notification(trip, notification_type):
        if notification_type == 'trip_reminder':
            message = f"Rappel : Vous avez un voyage prévu le {trip.start_time.strftime('%d/%m/%Y à %H:%M')} de {trip.route.name}"
        elif notification_type == 'trip_delay':
            message = f"Votre voyage de {trip.route.name} prévu à {trip.start_time.strftime('%H:%M')} est retardé."
        elif notification_type == 'trip_cancellation':
            message = f"Votre voyage de {trip.route.name} prévu à {trip.start_time.strftime('%H:%M')} a été annulé."

        for passenger in trip.passengers.all():
            NotificationService.create_notification(
                user=passenger.user,
                notification_type=notification_type,
                message=message,
                priority='high',
                action_url=f'/trip-details/{trip.id}/',
                related_object=trip
            )

    @staticmethod
    def service_disruption_notification(route, affected_users):
        message = f"Perturbation sur la ligne {route.name}. Veuillez prévoir un délai supplémentaire."
        for user in affected_users:
            NotificationService.create_notification(
                user=user,
                notification_type='service_disruption',
                message=message,
                priority='high',
                action_url=f'/route-status/{route.id}/',
                related_object=route
            )

    @staticmethod
    def route_change_notification(route, affected_users):
        message = f"Le trajet de la ligne {route.name} a été modifié. Veuillez vérifier les nouvelles informations."
        for user in affected_users:
            NotificationService.create_notification(
                user=user,
                notification_type='route_change',
                message=message,
                priority='medium',
                action_url=f'/route-details/{route.id}/',
                related_object=route
            )

    @staticmethod
    def maintenance_alert_notification(maintenance_info, affected_users):
        message = f"Maintenance prévue : {maintenance_info}. Des perturbations sont à prévoir."
        for user in affected_users:
            NotificationService.create_notification(
                user=user,
                notification_type='maintenance_alert',
                message=message,
                priority='medium',
                action_url='/maintenance-schedule/'
            )

    @staticmethod
    def card_notification(card, notification_type):
        if notification_type == 'card_expiring':
            days_left = (card.expiry_date - timezone.now().date()).days
            message = f"Votre carte de transport expire dans {days_left} jours. Pensez à la renouveler !"
        elif notification_type == 'card_expired':
            message = "Votre carte de transport a expiré. Veuillez la renouveler pour continuer à l'utiliser."
        elif notification_type == 'card_blocked':
            message = "Votre carte de transport a été bloquée. Veuillez contacter le service client pour plus d'informations."
        elif notification_type == 'card_replaced':
            message = "Votre carte de transport a été remplacée. La nouvelle carte est en cours d'envoi."

        NotificationService.create_notification(
            user=card.passenger.user,
            notification_type=notification_type,
            message=message,
            priority='high',
            action_url='/card-details/',
            related_object=card
        )

    @staticmethod
    def account_update_notification(user, update_type):
        message = f"Votre compte a été mis à jour : {update_type}"
        NotificationService.create_notification(
            user=user,
            notification_type='account_update',
            message=message,
            priority='medium',
            action_url='/account-settings/'
        )

    @staticmethod
    def password_change_notification(user):
        message = "Votre mot de passe a été modifié. Si vous n'êtes pas à l'origine de ce changement, contactez-nous immédiatement."
        NotificationService.create_notification(
            user=user,
            notification_type='password_change',
            message=message,
            priority='high',
            action_url='/account-security/'
        )

    @staticmethod
    def suspicious_activity_notification(user, activity_details):
        message = f"Activité suspecte détectée sur votre compte : {activity_details}"
        NotificationService.create_notification(
            user=user,
            notification_type='suspicious_activity',
            message=message,
            priority='urgent',
            action_url='/account-security/'
        )

    @staticmethod
    def login_from_new_device_notification(user, device_info):
        message = f"Nouvelle connexion détectée depuis : {device_info}"
        NotificationService.create_notification(
            user=user,
            notification_type='login_from_new_device',
            message=message,
            priority='high',
            action_url='/account-activity/'
        )

    @staticmethod
    def promo_offer_notification(user, offer_details):
        message = f"Nouvelle offre promotionnelle : {offer_details}"
        NotificationService.create_notification(
            user=user,
            notification_type='promo_offer',
            message=message,
            priority='low',
            action_url='/promotions/'
        )

    @staticmethod
    def new_feature_notification(feature_name, affected_users):
        message = f"Nouvelle fonctionnalité disponible : {feature_name}. Découvrez-la dès maintenant !"
        for user in affected_users:
            NotificationService.create_notification(
                user=user,
                notification_type='new_feature',
                message=message,
                priority='low',
                action_url='/new-features/'
            )

    @staticmethod
    def survey_invitation_notification(user, survey_details):
        message = f"Nous aimerions avoir votre avis ! {survey_details}"
        NotificationService.create_notification(
            user=user,
            notification_type='survey_invitation',
            message=message,
            priority='low',
            action_url='/surveys/'
        )

    @staticmethod
    def feedback_request_notification(user, trip):
        message = f"Comment s'est passé votre voyage du {trip.start_time.strftime('%d/%m/%Y')} ? Donnez-nous votre avis !"
        NotificationService.create_notification(
            user=user,
            notification_type='feedback_request',
            message=message,
            priority='low',
            action_url=f'/feedback/{trip.id}/',
            related_object=trip
        )

    @staticmethod
    def special_event_notification(event, affected_users):
        message = f"Événement spécial : {event.name}. {event.description}"
        for user in affected_users:
            NotificationService.create_notification(
                user=user,
                notification_type='special_event',
                message=message,
                priority='medium',
                action_url=f'/events/{event.id}/',
                related_object=event
            )

    @staticmethod
    def holiday_schedule_notification(holiday, affected_users):
        message = f"Horaires spéciaux pour {holiday.name}. Consultez les changements."
        for user in affected_users:
            NotificationService.create_notification(
                user=user,
                notification_type='holiday_schedule',
                message=message,
                priority='medium',
                action_url='/holiday-schedules/'
            )

    @staticmethod
    def vehicle_status_notification(vehicle, status):
        if status == 'arrival':
            message = f"Le véhicule {vehicle.number} est arrivé à l'arrêt."
        elif status == 'departure':
            message = f"Le véhicule {vehicle.number} est parti de l'arrêt."
        elif status == 'full':
            message = f"Le véhicule {vehicle.number} est complet."

        for passenger in vehicle.current_passengers.all():
            NotificationService.create_notification(
                user=passenger.user,
                notification_type=f'vehicle_{status}',
                message=message,
                priority='medium',
                related_object=vehicle
            )

    @staticmethod
    def document_expiring_notification(user, document):
        days_left = (document.expiry_date - timezone.now().date()).days
        message = f"Votre document {document.type} expire dans {days_left} jours. Pensez à le renouveler !"
        NotificationService.create_notification(
            user=user,
            notification_type='document_expiring',
            message=message,
            priority='medium',
            action_url='/documents/',
            related_object=document
        )

    @staticmethod
    def license_renewal_notification(driver):
        days_left = (driver.license_expiry_date - timezone.now().date()).days
        message = f"Votre licence de conducteur expire dans {days_left} jours. Renouvelez-la rapidement !"
        NotificationService.create_notification(
            user=driver.user,
            notification_type='license_renewal',
            message=message,
            priority='high',
            action_url='/license-renewal/',
            related_object=driver
        )

    @staticmethod
    def reservation_notification(reservation, notification_type):
        if notification_type == 'reservation_confirmation':
            message = f"Votre réservation pour le {reservation.date} a été confirmée."
        elif notification_type == 'reservation_reminder':
            message = f"Rappel : Vous avez une réservation pour le {reservation.date}."
        elif notification_type == 'reservation_change':
            message = f"Votre réservation pour le {reservation.date} a été modifiée."

        NotificationService.create_notification(
            user=reservation.user,
            notification_type=notification_type,
            message=message,
            priority='medium',
            action_url=f'/reservation/{reservation.id}/',
            related_object=reservation
        )

    @staticmethod
    def lost_and_found_notification(user, item):
            message = f"Un objet correspondant à la description '{item.description}' a été trouvé."
            NotificationService.create_notification(
                user=user,
                notification_type='lost_and_found',
                message=message,
                priority='medium',
                action_url='/lost-and-found/',
                related_object=item
            )

    @staticmethod
    def customer_support_notification(user, ticket):
            message = f"Mise à jour de votre ticket de support #{ticket.id}: {ticket.status}"
            NotificationService.create_notification(
                user=user,
                notification_type='customer_support',
                message=message,
                priority='medium',
                action_url=f'/support-ticket/{ticket.id}/',
                related_object=ticket
            )

    @staticmethod
    def system_update_notification(affected_users):
            message = "Une mise à jour du système est prévue. Certains services pourraient être temporairement indisponibles."
            for user in affected_users:
                NotificationService.create_notification(
                    user=user,
                    notification_type='system_update',
                    message=message,
                    priority='medium',
                    action_url='/system-status/'
                )

        # Méthodes utilitaires

    @staticmethod
    def send_bulk_notifications(users, notification_type, message, **kwargs):
            for user in users:
                NotificationService.create_notification(user, notification_type, message, **kwargs)

    @staticmethod
    def clear_old_notifications():
            # Supprime les notifications lues de plus de 30 jours
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            Notification.objects.filter(read=True, created_at__lt=thirty_days_ago).delete()

    @staticmethod
    def mark_all_as_read(user):
            Notification.objects.filter(user=user, read=False).update(read=True)

    @staticmethod
    def get_unread_notifications_count(user):
            return Notification.objects.filter(user=user, read=False).count()

        # Méthodes pour gérer les préférences de notification des utilisateurs

    @staticmethod
    def update_notification_preferences(user, preferences):
            # Mettez à jour les préférences de notification de l'utilisateur
            user.notification_preferences.update(**preferences)

    @staticmethod
    def should_send_notification(user, notification_type):
            # Vérifiez si l'utilisateur a choisi de recevoir ce type de notification
            return user.notification_preferences.get(notification_type, True)

        # Méthodes pour les notifications en temps réel (si applicable)

    @staticmethod
    def send_real_time_notification(user, message):
            # Implémentez ici la logique pour envoyer une notification en temps réel
            # Par exemple, en utilisant WebSockets ou une technologie similaire
            pass

        # Méthodes pour les rapports et analyses

    @staticmethod
    def generate_notification_report(start_date, end_date):
            # Générez un rapport sur les notifications envoyées pendant une période donnée
            return Notification.objects.filter(created_at__range=[start_date, end_date]).values('notification_type').annotate(count=models.Count('id'))

    @staticmethod
    def get_most_common_notification_types(limit=5):
            # Obtenez les types de notifications les plus courants
            return Notification.objects.values('notification_type').annotate(count=models.Count('id')).order_by('-count')[:limit]

        # Méthodes pour la gestion des erreurs et la journalisation

    #@staticmethod
    #def log_notification_error(notification, error):
            # Journalisez les erreurs survenues lors de l'envoi des notifications
            # Vous pouvez implémenter cela en utilisant le système de journalisation de Django ou un service tiers
            #logger.error(f"Erreur lors de l'envoi de la notification {notification.id}: {error}")

        # Méthodes pour les tests et le débogage

    @staticmethod
    def send_test_notification(user):
            # Envoyez une notification de test à l'utilisateur
            NotificationService.create_notification(
                user=user,
                notification_type='test',
                message="Ceci est une notification de test.",
                priority='low'
            )

    @staticmethod
    def get_notification_history(user):
            # Obtenez l'historique complet des notifications pour un utilisateur
            return Notification.objects.filter(user=user).order_by('-created_at')