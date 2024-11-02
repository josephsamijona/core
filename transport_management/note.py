from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from .schedule import Schedule
from .route import Route
from .driver import Driver
from .vehicle import Vehicle
from .destination import Destination
from django.contrib.auth import get_user_model

User = get_user_model()

class Trip(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planifié'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
        ('delayed', 'Retardé'),
        ('interrupted', 'Interrompu'),
        ('rescheduled', 'Reprogrammé')
    ]

    TRIP_TYPE_CHOICES = [
        ('regular', 'Régulier'),
        ('express', 'Express'),
        ('shuttle', 'Navette'),
        ('special', 'Spécial'),
        ('emergency', 'Urgence')
    ]

    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('medium', 'Moyenne'),
        ('high', 'Haute'),
        ('urgent', 'Urgente')
    ]

    # Relations principales
    schedule = models.ForeignKey(
        Schedule, 
        on_delete=models.CASCADE,
        related_name='trips',
        help_text="Schedule associé à ce voyage"
    )
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='trips_as_driver')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    rule_set = models.ForeignKey('RuleSet', on_delete=models.SET_NULL, null=True, help_text="Ensemble de règles appliquées à ce voyage")
    # Informations temporelles
    trip_date = models.DateTimeField(default=timezone.now, help_text="Date et heure du voyage")
    planned_departure = models.DateTimeField(help_text="Heure de départ prévue")
    planned_arrival = models.DateTimeField(help_text="Heure d'arrivée prévue")
    departure_time = models.DateTimeField(null=True, blank=True, help_text="Heure de départ réelle")
    arrival_time = models.DateTimeField(null=True, blank=True, help_text="Heure d'arrivée réelle")
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)

    # Caractéristiques du voyage
    origin = models.CharField(max_length=255, help_text="Lieu de départ")
    passenger_count = models.PositiveIntegerField(default=0, help_text="Nombre de passagers")
    max_capacity = models.PositiveIntegerField(help_text="Capacité maximale")
    trip_type = models.CharField(max_length=20, choices=TRIP_TYPE_CHOICES, default='regular')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')

    # Statut et suivi
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    delay_duration = models.DurationField(null=True, blank=True, help_text="Durée du retard")
    real_time_incidents = models.JSONField(default=list, help_text="Incidents survenus")
    weather_conditions = models.JSONField(default=dict, help_text="Conditions météo")
    traffic_conditions = models.JSONField(default=dict, help_text="Conditions de circulation")

    # Schedule Conformité
    schedule_adherence = models.CharField(
        max_length=20,
        choices=[
            ('on_time', 'À l\'heure'),
            ('early', 'En avance'),
            ('delayed', 'En retard'),
            ('unknown', 'Non déterminé')
        ],
        default='unknown'
    )
    delay_minutes = models.IntegerField(default=0)

    # Validation et conformité
    validation_status = models.JSONField(default=dict, help_text="État des validations")
    rule_violations = models.JSONField(default=list, help_text="Violations de règles")
    safety_checks = models.JSONField(default=dict, help_text="Vérifications de sécurité")

    # Suivi des modifications
    modification_history = models.JSONField(default=list, help_text="Historique des modifications")
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='trip_modifications')
    modification_reason = models.TextField(blank=True)

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='trips_created')
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Trip"
        verbose_name_plural = "Trips"
        ordering = ['-trip_date', 'priority']
        indexes = [
            models.Index(fields=['schedule', 'status']),
            models.Index(fields=['planned_departure', 'status']),
            models.Index(fields=['route', 'trip_date'])
        ]
    def __str__(self):
        return f"Trip {self.id} - {self.trip_date} - {self.route.name}"

    def clean(self):
        """Validation des données avant sauvegarde"""
        super().clean()
        if self.planned_departure:
            if not self.schedule.is_valid_for_date(self.planned_departure.date()):
                raise ValidationError("La date de départ n'est pas valide pour ce schedule")
            if self.planned_arrival <= self.planned_departure:
                raise ValidationError("L'heure d'arrivée doit être postérieure à l'heure de départ")

    def validate_rules(self, action_type):
        """Valide les règles applicables pour une action donnée"""
        if self.rule_set:
            rules = self.rule_set.rules.filter(rule_type='trip')
            validation_results = {
                'valid': True,
                'violations': [],
                'warnings': []
            }
            return validation_results
        return {'valid': True, 'violations': [], 'warnings': []}

    def log_modification(self, action_type, reason=''):
        """Enregistre une modification dans l'historique"""
        modification = {
            'action': action_type,
            'timestamp': timezone.now().isoformat(),
            'user': self.modified_by.username if self.modified_by else 'System',
            'reason': reason or self.modification_reason
        }
        if isinstance(self.modification_history, list):
            self.modification_history.append(modification)
        else:
            self.modification_history = [modification]

    def start_trip(self):
        """Démarre le voyage avec validation des règles"""
        rule_check = self.validate_rules('start_trip')
        if rule_check['valid']:
            self.status = 'in_progress'
            self.departure_time = timezone.now()
            self.actual_start_time = timezone.now()
            self.calculate_schedule_adherence()
            self.log_modification('start_trip')
            self.save()
        return rule_check

    def end_trip(self):
        """Termine le voyage avec validation"""
        rule_check = self.validate_rules('end_trip')
        if rule_check['valid']:
            self.status = 'completed'
            self.arrival_time = timezone.now()
            self.actual_end_time = timezone.now()
            self.calculate_schedule_adherence()
            # Mettre à jour les métriques du schedule
            self.schedule.update_schedule_metrics()
            self.log_modification('end_trip')
            self.save()
        return rule_check

    def cancel_trip(self, reason=''):
        """Annule le voyage avec raison"""
        self.status = 'cancelled'
        self.log_modification('cancel_trip', reason)
        self.save()
        self.schedule.update_schedule_metrics()

    def add_incident(self, incident_description, severity='medium'):
        """Ajoute un incident avec plus de détails"""
        incident = {
            'description': incident_description,
            'timestamp': timezone.now().isoformat(),
            'severity': severity,
            'status': 'open',
            'schedule_impact': self.calculate_schedule_adherence()
        }
        if isinstance(self.real_time_incidents, list):
            self.real_time_incidents.append(incident)
        else:
            self.real_time_incidents = [incident]
        self.log_modification('add_incident')
        self.save()

    def increment_passenger_count(self):
        """Incrémente le nombre de passagers avec vérification de capacité"""
        if self.passenger_count < self.max_capacity:
            self.passenger_count += 1
            self.log_modification('increment_passenger')
            self.save()
        else:
            raise ValueError("Maximum capacity reached")

    def update_delay(self, delay_minutes):
        """Met à jour le retard du voyage"""
        self.delay_duration = timedelta(minutes=delay_minutes)
        self.delay_minutes = delay_minutes
        if delay_minutes > 0:
            self.status = 'delayed'
            self.schedule_adherence = 'delayed'
        self.log_modification('update_delay')
        self.save()
        # Informer le schedule du retard
        self.schedule.update_schedule_metrics()

    def calculate_schedule_adherence(self):
        """Calcule l'adhérence au schedule"""
        if not self.departure_time:
            return 'unknown'
        
        delay = (self.departure_time - self.planned_departure).total_seconds() / 60
        self.delay_minutes = int(delay)
        
        if abs(delay) <= 5:  # 5 minutes de tolérance
            self.schedule_adherence = 'on_time'
        elif delay < 0:
            self.schedule_adherence = 'early'
        else:
            self.schedule_adherence = 'delayed'
        
        return self.schedule_adherence

    def get_trip_duration(self):
        """Calcule la durée du voyage"""
        if self.actual_end_time and self.actual_start_time:
            return self.actual_end_time - self.actual_start_time
        return None

    def check_safety_requirements(self):
        """Vérifie les exigences de sécurité"""
        safety_status = {
            'vehicle_check': self.vehicle.check_safety_status(),
            'driver_check': self.driver.check_eligibility(),
            'weather_check': self.check_weather_conditions(),
            'last_check_time': timezone.now().isoformat()
        }
        self.safety_checks = safety_status
        self.save()
        return safety_status

    def update_weather_conditions(self, conditions):
        """Met à jour les conditions météo"""
        self.weather_conditions.update(conditions)
        self.save()