from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('admin', 'Admin'),
        ('receptionist', 'Receptionist'),
        ('driver', 'Driver'),
        ('parent', 'Parent'),
        ('etudiant', 'Étudiant'),
        ('special', 'Spécial'),
        ('employee', 'Employé'),
    ]
    
    # Les champs username, email, password, first_name (Name), et last_name (Surname) 
    # sont déjà inclus dans AbstractUser

    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='etudiant')
    sex = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    telephone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

class Eleve(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='eleve', limit_choices_to={'user_type': 'etudiant'})
    parent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='enfants', limit_choices_to={'user_type': 'parent'})
    classe = models.CharField(max_length=50)
    numero_etudiant = models.CharField(max_length=20, unique=True)
    

    def __str__(self):
        return f"{self.user.username} - {self.classe}"

class Permission(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class DeviceInfo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device_name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=50)
    last_login = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s {self.device_type}"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        # Abonnements et paiements
        ('subscription_expiring', _('Abonnement sur le point d\'expirer')),
        ('subscription_expired', _('Abonnement expiré')),
        ('auto_renewal', _('Renouvellement automatique')),
        ('payment_success', _('Paiement réussi')),
        ('payment_failed', _('Échec du paiement')),
        ('payment_due', _('Paiement dû')),
        ('price_change', _('Changement de tarif')),
        
        # Voyages et perturbations
        ('trip_reminder', _('Rappel de voyage')),
        ('trip_delay', _('Retard de voyage')),
        ('trip_cancellation', _('Annulation de voyage')),
        ('service_disruption', _('Perturbation de service')),
        ('route_change', _('Changement itinéraire')),
        ('maintenance_alert', _('Alerte de maintenance')),
        
        # Carte de transport
        ('card_expiring', _('Carte sur le point d\'expirer')),
        ('card_expired', _('Carte expirée')),
        ('card_blocked', _('Carte bloquée')),
        ('card_replaced', _('Carte remplacée')),
        
        # Compte et sécurité
        ('account_update', _('Mise à jour du compte')),
        ('password_change', _('Changement de mot de passe')),
        ('suspicious_activity', _('Activité suspecte détectée')),
        ('login_from_new_device', _('Connexion depuis un nouvel appareil')),
        
        # Marketing et informations
        ('promo_offer', _('Offre promotionnelle')),
        ('new_feature', _('Nouvelle fonctionnalité')),
        ('survey_invitation', _('Invitation à un sondage')),
        ('feedback_request', _('Demande de retour d\'expérience')),
        
        # Événements spéciaux
        ('special_event', _('Événement spécial')),
        ('holiday_schedule', _('Horaires des jours fériés')),
        
        # Statut du véhicule
        ('vehicle_arrival', _('Arrivée du véhicule')),
        ('vehicle_departure', _('Départ du véhicule')),
        ('vehicle_full', _('Véhicule complet')),
        
        # Rappels et renouvellements
        ('document_expiring', _('Document sur le point d\'expirer')),
        ('license_renewal', _('Renouvellement de licence')),
        
        # Réservations
        ('reservation_confirmation', _('Confirmation de réservation')),
        ('reservation_reminder', _('Rappel de réservation')),
        ('reservation_change', _('Modification de réservation')),
        
        # Autres
        ('lost_and_found', _('Objets trouvés')),
        ('customer_support', _('Support client')),
        ('system_update', _('Mise à jour du système')),
    ]

    PRIORITY_LEVELS = [
        ('low', _('Basse')),
        ('medium', _('Moyenne')),
        ('high', _('Haute')),
        ('urgent', _('Urgente')),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='medium')
    action_url = models.URLField(blank=True, null=True)
    expiration_date = models.DateTimeField(null=True, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object_type = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.user.username}: {self.message[:50]}..."

    def mark_as_read(self):
        self.read = True
        self.save()

    @property
    def is_expired(self):
        if self.expiration_date:
            from django.utils import timezone
            return timezone.now() > self.expiration_date
        return False

class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback from {self.user.username} - Rating: {self.rating}"

class UserLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    details = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp}"