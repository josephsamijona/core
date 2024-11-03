from django.db import models
import uuid
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from user_management.models import User

User = get_user_model()

class UserType(models.TextChoices):
    PARENT = 'P', 'Parent'
    EMPLOYEE = 'E', 'Employee'
    STUDENT = 'S', 'Student'

class Status(models.TextChoices):
    NOT_IN_CIRCULATION = 'not_in_circulation', 'Not in Circulation'
    ASSIGNED = 'assigned', 'Assigned'
    AVAILABLE = 'available', 'Available'

class CardAssignmentid(models.Model):
    user_type = models.CharField(
        max_length=1,
        choices=UserType.choices,
        default=UserType.STUDENT,
        help_text="The type of user: Parent, Employee, or Student."
    )
    unique_code = models.CharField(
        max_length=50,
        unique=True,
        help_text="The unique card assignment number for each user."
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_IN_CIRCULATION,
        help_text="The card status (Not in Circulation, Assigned, or Available)."
    )
    assigned_on = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.unique_code:
            self.unique_code = self.generate_unique_code()
        super().save(*args, **kwargs)

    def generate_unique_code(self):
        # Your logic to generate a unique code
        pass

    def __str__(self):
        return f"{self.unique_code} ({self.get_user_type_display()})"

class SubscriptionPlan(models.Model):
    USER_TYPE_CHOICES = [
        ('parent', 'Parent'),
        ('employee', 'Employé'),
        ('student', 'Étudiant'),
        ('special', 'Spécial'),
    ]
    DURATION_CHOICES = [
        ('monthly', 'Mensuel'),
        ('quarterly', 'Trimestriel'),
    ]
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    circuit = models.CharField(max_length=50)  # A, B, ou C
    locality = models.CharField(max_length=100)
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)

    class Meta:
        unique_together = ('user_type', 'circuit', 'locality', 'duration')

    def __str__(self):
        return f"{self.get_user_type_display()} - Circuit {self.circuit} - {self.locality} - {self.get_duration_display()}"

class PassengerUser(models.Model):
    ACCOUNT_STATUS_CHOICES = [
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
        ('suspended', 'Suspendu'),
        ('pending', 'En attente'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='passenger_profile')
    account_status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default='pending')
    emergency_contact = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.user.get_user_type_display()})"

@receiver(post_save, sender=User)
def create_or_update_passenger_user(sender, instance, created, **kwargs):
    passenger_types = ['parent', 'etudiant', 'special', 'employee']
    if instance.user_type in passenger_types:
        PassengerUser.objects.update_or_create(
            user=instance,
            defaults={'account_status': 'active' if created else 'pending'}
        )
    
    
class CardInfo(models.Model):
    CARD_TYPE_CHOICES = [
        ('rfid', 'RFID'),
        ('nfc', 'NFC'),
        ('qr', 'QR Code'),
    ]
    is_mobile_nfc = models.BooleanField(default=False)
    mobile_device_id = models.CharField(max_length=255, null=True, blank=True)
    card_assignment = models.OneToOneField(
        CardAssignmentid, on_delete=models.CASCADE, related_name='card_info'
    )
    passenger = models.ForeignKey(
        PassengerUser, on_delete=models.CASCADE, related_name='cards'
    )
    card_type = models.CharField(max_length=10, choices=CARD_TYPE_CHOICES)
    nfc_id = models.CharField(max_length=255, null=True, blank=True)
    issue_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)  # Added field
    updated_at = models.DateTimeField(auto_now_add=True, null=True)      # Added field

    def __str__(self):
        return f"{self.card_assignment.unique_code} ({self.get_card_type_display()}) - {self.passenger.user.get_full_name()}"



class Subscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
    ]
    
    passenger = models.ForeignKey(PassengerUser, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    card = models.ForeignKey(CardInfo, on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    auto_renew = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.passenger.user.get_full_name()} - {self.plan}"

    def is_active(self):
        return self.status == 'active' and self.start_date <= timezone.now().date() <= self.end_date

class TransportCard(models.Model):
    card_info = models.OneToOneField(CardInfo, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Card for {self.card_info.passenger.user.get_full_name()}"

    def is_valid(self):
        return self.card_info.is_active and (self.card_info.passenger.subscription_set.filter(status='active', card=self.card_info).exists() or self.balance > 0)
    
    
class TemporaryVirtualCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    passenger = models.ForeignKey(PassengerUser, on_delete=models.CASCADE, related_name='virtual_cards')
    qr_code = models.TextField()  # Stockera l'information encodée dans le QR code
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=30)
        super().save(*args, **kwargs)
        
class Payment(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('subscription', 'Abonnement'),
        ('registration', 'Frais d\'inscription'),
        ('top_up', 'Rechargement'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('completed', 'Complété'),
        ('failed', 'Échoué'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    payment_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True)

class Balance(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)

class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20)  # 'debit' ou 'credit'
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)



class BoardingSession(models.Model):
   STATUS_CHOICES = [
       ('active', 'Active'),
       ('paused', 'Paused'),
       ('ended', 'Ended'),
       ('expired', 'Expired'),
       ('interrupted', 'Interrupted')
   ]

   session_id = models.UUIDField(
       default=uuid.uuid4, 
       unique=True, 
       editable=False,
       help_text="Identifiant unique de la session"
   )
   trip = models.ForeignKey(
       'transport_management.Trip', 
       on_delete=models.CASCADE,
       related_name='boarding_sessions'
   )
   device_id = models.CharField(
       max_length=255,
       help_text="Identifiant unique du dispositif"
   )
   start_time = models.DateTimeField(
       default=timezone.now,
       help_text="Heure de début de la session"
   )
   end_time = models.DateTimeField(
       null=True, 
       blank=True,
       help_text="Heure de fin de la session"
   )
   status = models.CharField(
       max_length=20,
       choices=STATUS_CHOICES,
       default='active'
   )
   offline_mode = models.BooleanField(
       default=False,
       help_text="Indique si la session est en mode hors-ligne"
   )
   last_sync = models.DateTimeField(
       auto_now=True,
       help_text="Dernière synchronisation"
   )
   session_data = models.JSONField(
       default=dict,
       help_text="Configuration et données de la session"
   )
   created_at = models.DateTimeField(auto_now_add=True)
   updated_at = models.DateTimeField(auto_now=True)

   class Meta:
       verbose_name = "Boarding Session"
       verbose_name_plural = "Boarding Sessions"
       ordering = ['-start_time']
       indexes = [
           models.Index(fields=['session_id']),
           models.Index(fields=['device_id', 'status']),
       ]

   def __str__(self):
       return f"Session {self.session_id} - Trip {self.trip_id}"

class BoardingValidation(models.Model):
   VALIDATION_TYPE_CHOICES = [
       ('online', 'Online'),
       ('offline', 'Offline')
   ]
   
   VALIDATION_STATUS_CHOICES = [
       ('pending', 'En attente'),
       ('successful', 'Réussi'),
       ('failed', 'Échoué'),
       ('cancelled', 'Annulé'),
       ('error', 'Erreur')
   ]

   validation_id = models.UUIDField(
       default=uuid.uuid4, 
       unique=True, 
       editable=False
   )
   boarding_session = models.ForeignKey(
       BoardingSession,
       on_delete=models.CASCADE,
       related_name='validations'
   )
   transaction_scan = models.ForeignKey(
       'transport_management.TransactionScan',
       on_delete=models.CASCADE,
       related_name='boarding_validations'
   )
   passenger_trip = models.ForeignKey(
       'transport_management.PassengerTrip',
       on_delete=models.CASCADE,
       related_name='boarding_validations'
   )
   validation_time = models.DateTimeField(
       default=timezone.now,
       help_text="Moment de la validation"
   )
   validation_type = models.CharField(
       max_length=20,
       choices=VALIDATION_TYPE_CHOICES,
       default='online'
   )
   validation_status = models.CharField(
       max_length=20,
       choices=VALIDATION_STATUS_CHOICES,
       default='pending'
   )
   validation_details = models.JSONField(
       default=dict,
       help_text="Détails de la validation"
   )
   created_at = models.DateTimeField(auto_now_add=True)
   updated_at = models.DateTimeField(auto_now=True)

   class Meta:
       verbose_name = "Boarding Validation"
       verbose_name_plural = "Boarding Validations"
       ordering = ['-validation_time']

   def __str__(self):
       return f"Validation {self.validation_id} - {self.validation_status}"

class BoardingDevice(models.Model):
   DEVICE_TYPE_CHOICES = [
       ('mobile', 'Mobile'),
       ('desktop', 'Desktop'),
       ('web', 'Web')
   ]
   
   DEVICE_STATUS_CHOICES = [
       ('active', 'Active'),
       ('inactive', 'Inactive'),
       ('maintenance', 'Maintenance'),
       ('blocked', 'Blocked')
   ]

   device_id = models.CharField(
       max_length=255,
       unique=True,
       help_text="Identifiant unique du dispositif"
   )
   device_type = models.CharField(
       max_length=20,
       choices=DEVICE_TYPE_CHOICES
   )
   device_specs = models.JSONField(
       default=dict,
       help_text="Caractéristiques du dispositif"
   )
   nfc_capabilities = models.JSONField(
       default=dict,
       help_text="Capacités NFC pour Android"
   )
   registration_token = models.CharField(
       max_length=255,
       unique=True,
       help_text="Token d'enregistrement"
   )
   last_active = models.DateTimeField(
       default=timezone.now
   )
   status = models.CharField(
       max_length=20,
       choices=DEVICE_STATUS_CHOICES,
       default='active'
   )
   created_at = models.DateTimeField(auto_now_add=True)
   updated_at = models.DateTimeField(auto_now=True)

   class Meta:
       verbose_name = "Boarding Device"
       verbose_name_plural = "Boarding Devices"
       indexes = [
           models.Index(fields=['device_id', 'status']),
       ]

class BoardingError(models.Model):
   ERROR_TYPE_CHOICES = [
       ('validation', 'Validation Error'),
       ('device', 'Device Error'),
       ('sync', 'Synchronization Error'),
       ('network', 'Network Error'),
       ('system', 'System Error')
   ]

   error_id = models.UUIDField(
       default=uuid.uuid4,
       unique=True,
       editable=False
   )
   boarding_session = models.ForeignKey(
       BoardingSession,
       on_delete=models.CASCADE,
       related_name='errors'
   )
   error_type = models.CharField(
       max_length=50,
       choices=ERROR_TYPE_CHOICES
   )
   error_details = models.JSONField(
       default=dict,
       help_text="Détails de l'erreur"
   )
   timestamp = models.DateTimeField(
       default=timezone.now
   )
   resolved = models.BooleanField(
       default=False
   )
   resolution_details = models.JSONField(
       null=True,
       blank=True,
       help_text="Détails de la résolution"
   )
   created_at = models.DateTimeField(auto_now_add=True)
   updated_at = models.DateTimeField(auto_now=True)

   class Meta:
       verbose_name = "Boarding Error"
       verbose_name_plural = "Boarding Errors"
       ordering = ['-timestamp']

class BoardingConfiguration(models.Model):
   DEVICE_TYPE_CHOICES = [
       ('all', 'All Devices'),
       ('mobile', 'Mobile'),
       ('desktop', 'Desktop'),
       ('web', 'Web')
   ]

   config_key = models.CharField(
       max_length=255,
       unique=True,
       help_text="Clé de configuration unique"
   )
   config_value = models.JSONField(
       default=dict,
       help_text="Valeur de configuration"
   )
   device_type = models.CharField(
       max_length=20,
       choices=DEVICE_TYPE_CHOICES,
       default='all'
   )
   active = models.BooleanField(
       default=True
   )
   created_at = models.DateTimeField(auto_now_add=True)
   updated_at = models.DateTimeField(auto_now=True)

   class Meta:
       verbose_name = "Boarding Configuration"
       verbose_name_plural = "Boarding Configurations"
       unique_together = ['config_key', 'device_type']

class ValidationRule(models.Model):
   RULE_TYPE_CHOICES = [
       ('boarding', 'Boarding Rule'),
       ('capacity', 'Capacity Rule'),
       ('timing', 'Timing Rule'),
       ('security', 'Security Rule')
   ]

   rule_type = models.CharField(
       max_length=50,
       choices=RULE_TYPE_CHOICES
   )
   rule_definition = models.JSONField(
       help_text="Définition de la règle"
   )
   priority = models.IntegerField(
       default=0,
       help_text="Priorité de la règle"
   )
   active = models.BooleanField(
       default=True
   )
   created_at = models.DateTimeField(auto_now_add=True)
   updated_at = models.DateTimeField(auto_now=True)

   class Meta:
       verbose_name = "Validation Rule"
       verbose_name_plural = "Validation Rules"
       ordering = ['priority']
       indexes = [
           models.Index(fields=['rule_type', 'active']),
       ]

   def __str__(self):
       return f"{self.get_rule_type_display()} - Priority {self.priority}"
   
# boarding/models.py

class OfflineValidation(models.Model):
    passenger = models.ForeignKey(PassengerUser, on_delete=models.CASCADE)
    trip = models.ForeignKey('transport_management.Trip', on_delete=models.CASCADE)
    scan_type = models.CharField(max_length=10)  # 'nfc' ou 'qr'
    timestamp = models.DateTimeField()
    data = models.TextField()  # Stocke les données brutes en JSON
    status = models.CharField(max_length=10)  # 'pending', 'synced', 'failed'
    synchronized_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"OfflineValidation {self.id} - {self.status}"
