from django.db import models
from django.conf import settings
from django.db.models import Avg
from geopy.distance import geodesic
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from inventory_management.models import Vehicle
from membership_management.models import CardInfo
from datetime import timedelta, time, datetime, date
from geopy.geocoders import Nominatim
from django.core.cache import cache
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()

class OperationalRule(models.Model):
    RULE_TYPE_CHOICES = [
        ('scheduling', 'Scheduling'),
        ('assignment', 'Resource Assignment'),
        ('routing', 'Routing'),
        ('pricing', 'Pricing'),
        ('maintenance', 'Maintenance'),
        ('emergency', 'Emergency Response'),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    rule_type = models.CharField(max_length=50, choices=RULE_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    conditions = models.JSONField()
    actions = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"

    class Meta:
        ordering = ['priority', 'rule_type', 'name']

class RuleExecution(models.Model):
    rule = models.ForeignKey(OperationalRule, on_delete=models.CASCADE)
    executed_at = models.DateTimeField(default=timezone.now)
    success = models.BooleanField()
    result = models.JSONField(null=True, blank=True)
    affected_entities = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Execution of {self.rule.name} at {self.executed_at}"

class RuleParameter(models.Model):
    PARAMETER_TYPE_CHOICES = [
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('string', 'String'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
    ]

    rule = models.ForeignKey(OperationalRule, on_delete=models.CASCADE, related_name='parameters')
    name = models.CharField(max_length=100)
    parameter_type = models.CharField(max_length=20, choices=PARAMETER_TYPE_CHOICES)
    default_value = models.JSONField(null=True, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.rule.name} - {self.name}"

    class Meta:
        unique_together = ['rule', 'name']

class RuleSet(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    rules = models.ManyToManyField(OperationalRule, through='RuleSetMembership')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class RuleSetMembership(models.Model):
    rule_set = models.ForeignKey(RuleSet, on_delete=models.CASCADE)
    rule = models.ForeignKey(OperationalRule, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']
        unique_together = ['rule_set', 'rule']

    def __str__(self):
        return f"{self.rule_set.name} - {self.rule.name} (Order: {self.order})"
    






class Destination(models.Model):
    # Informations de base
    name = models.CharField(max_length=255, help_text="Nom de la destination")
    locality = models.CharField(max_length=255, help_text="Localité de la destination")
    zone_code = models.CharField(max_length=10, help_text="Code de la zone géographique")
    circuit = models.CharField(max_length=50, help_text="Circuit associé à cette destination")

    # Localisation
    address = models.CharField(max_length=255, help_text="Adresse physique")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    gps_coordinates = models.CharField(max_length=255, blank=True, help_text="Format: lat,long")

    # Catégorisation
    category = models.CharField(max_length=50, choices=[
        ('business', 'Zone d\'affaires'),
        ('residential', 'Zone résidentielle'),
        ('educational', 'Zone éducative'),
        ('tourist', 'Zone touristique'),
        ('shopping', 'Zone commerciale')
    ])
    destination_type = models.CharField(max_length=50, choices=[
        ('primary', 'Primaire'),
        ('secondary', 'Secondaire'),
        ('terminal', 'Terminal'),
        ('hub', 'Hub'),
        ('tourist', 'Touristique')
    ])

    # Caractéristiques
    description = models.TextField(help_text="Description détaillée de la destination")
    facilities_available = models.JSONField(default=list, help_text="Liste des installations disponibles")
    accessibility_features = models.JSONField(default=list)
    parking_available = models.BooleanField(default=False)
    is_accessible = models.BooleanField(default=False)

    # Trafic et timing
    peak_hours = models.JSONField(default=dict, help_text="Heures de pointe par jour")
    estimated_daily_traffic = models.IntegerField(default=0)
    recommended_visit_times = models.JSONField(default=dict)
    service_hours = models.JSONField(default=dict)

    # Contacts et urgence
    emergency_contact = models.CharField(max_length=50, null=True, blank=True)
    support_phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    # Métadonnées
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def clean(self):
        if not self.gps_coordinates and self.latitude and self.longitude:
            self.gps_coordinates = f"{self.latitude},{self.longitude}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['name', 'locality']
        unique_together = ['name', 'locality', 'zone_code']

    def __str__(self):
        return f"{self.name} - {self.locality} ({self.zone_code})"

class Route(models.Model):
    # Informations de base
    name = models.CharField(max_length=255, help_text="Nom ou numéro de la route")
    description = models.TextField()
    route_code = models.CharField(max_length=20, unique=True)
    circuit = models.CharField(max_length=50)

    # Relations
    destinations = models.ManyToManyField(Destination, related_name='routes')
    alternate_routes = models.ManyToManyField('self', blank=True, symmetrical=False)

    # Catégorisation
    route_category = models.CharField(max_length=50, choices=[
        ('express', 'Express'),
        ('local', 'Local'),
        ('shuttle', 'Navette'),
        ('night', 'Service de nuit'),
        ('special', 'Service spécial')
    ])
    difficulty_level = models.CharField(max_length=20, choices=[
        ('easy', 'Facile'),
        ('medium', 'Moyen'),
        ('hard', 'Difficile')
    ])

    # Caractéristiques opérationnelles
    type = models.CharField(max_length=50, help_text="Type de la route")
    direction = models.CharField(max_length=50, help_text="Direction principale")
    total_distance = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_duration = models.DurationField()
    service_hours = models.CharField(max_length=100)
    operating_days = models.JSONField(default=list)

    # Fréquences
    peak_frequency = models.IntegerField(help_text="Fréquence en minutes (heures de pointe)")
    off_peak_frequency = models.IntegerField(help_text="Fréquence en minutes (heures creuses)")
    weekend_frequency = models.IntegerField(help_text="Fréquence en minutes (week-end)")

    # Caractéristiques techniques
    path = models.JSONField(help_text="Coordonnées détaillées du trajet")
    route_color = models.CharField(max_length=7, help_text="Code couleur HEX")
    traffic_conditions = models.JSONField(default=dict)
    elevation_profile = models.JSONField(default=dict)

    # Restrictions et conditions
    vehicle_type_restrictions = models.JSONField(default=list)
    weather_restrictions = models.JSONField(default=dict)
    seasonal_variations = models.JSONField(default=dict)

    # Métadonnées
    status = models.CharField(max_length=50, choices=[
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('planned', 'Planifiée'),
        ('modified', 'Modifiée')
    ])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def calculate_metrics(self):
        total_distance = 0
        previous_destination = None
        for destination in self.destinations.all().order_by('id'):
            if previous_destination:
                coords_1 = (previous_destination.latitude, previous_destination.longitude)
                coords_2 = (destination.latitude, destination.longitude)
                distance = geodesic(coords_1, coords_2).kilometers
                total_distance += distance
            previous_destination = destination
        self.total_distance = total_distance
        # Supposons une vitesse moyenne de 50 km/h
        self.estimated_duration = timedelta(hours=total_distance / 50)
        
    def __str__(self):
        return f"{self.name} ({self.route_category})"

    class Meta:
        ordering = ['name']
        unique_together = ['route_code', 'circuit']

class Stop(models.Model):
    # Informations de base
    name = models.CharField(max_length=255)
    stop_code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)

    # Localisation
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address = models.CharField(max_length=255)
    service_zone = models.CharField(max_length=100)
    platform_number = models.CharField(max_length=5, blank=True)
    zone_code = models.CharField(max_length=10)

    # Relations
    destination = models.ForeignKey(Destination, on_delete=models.SET_NULL, null=True, blank=True)

    # Caractéristiques physiques
    stop_type = models.CharField(max_length=50, choices=[
        ('bus_stop', 'Arrêt de bus'),
        ('station', 'Station'),
        ('terminal', 'Terminal'),
        ('connection_point', 'Point de connexion')
    ])
    shelter_available = models.BooleanField(default=False)
    lighting_available = models.BooleanField(default=False)
    seating_capacity = models.IntegerField(default=0)
    accessibility_features = models.JSONField(default=list)
    facilities = models.JSONField(default=list)
    amenities = models.JSONField(default=list)

    # Caractéristiques opérationnelles
    peak_hours_capacity = models.IntegerField(default=0)
    average_waiting_time = models.IntegerField(default=0)
    boarding_type = models.CharField(max_length=50, choices=[
        ('standard', 'Standard'),
        ('pre_boarding', 'Pré-embarquement'),
        ('all_door', 'Toutes portes')
    ])

    # Sécurité et maintenance
    security_features = models.JSONField(default=list)
    maintenance_schedule = models.JSONField(default=dict)
    last_inspection_date = models.DateField(null=True)
    next_maintenance_date = models.DateField(null=True)

    # Métadonnées
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=50, choices=[
        ('operational', 'Opérationnel'),
        ('maintenance', 'En maintenance'),
        ('closed', 'Fermé')
    ])
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['zone_code', 'name']
        unique_together = ['stop_code', 'platform_number']

    def __str__(self):
        return f"{self.name} ({self.stop_code})"

class RouteStop(models.Model):
    # Relations
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE)

    # Positionnement
    order = models.IntegerField()
    stop_sequence = models.IntegerField()
    distance_from_start = models.DecimalField(max_digits=8, decimal_places=2)

    # Timing
    estimated_time = models.IntegerField(help_text="Temps estimé depuis le début en minutes")
    dwell_time = models.IntegerField(default=30, help_text="Temps d'arrêt en secondes")
    is_timepoint = models.BooleanField(default=False)

    # Opérations
    stop_announcement = models.CharField(max_length=255)
    passenger_exchange = models.JSONField(default=dict)
    stop_restrictions = models.JSONField(default=list)
    pickup_type = models.IntegerField(choices=[
        (0, 'Régulier'),
        (1, 'Pas de ramassage'),
        (2, 'Sur appel'),
        (3, 'Sur arrangement')
    ])
    drop_off_type = models.IntegerField(choices=[
        (0, 'Régulier'),
        (1, 'Pas de dépose'),
        (2, 'Sur appel'),
        (3, 'Sur arrangement')
    ])

    # Connexions
    connection_routes = models.ManyToManyField(Route, related_name='connected_stops')
    transfer_time = models.IntegerField(default=0, help_text="Temps de correspondance en minutes")

    # Métadonnées
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['route', 'order']
        unique_together = [
            ('route', 'stop', 'order'),
            ('route', 'stop_sequence')
        ]

    def __str__(self):
        return f"{self.route.name} - Stop {self.stop.name} (Order: {self.order})"


class Schedule(models.Model):
    # Relations
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='schedules')
    destination = models.ForeignKey(
        Destination,
        on_delete=models.CASCADE,
        related_name='schedules',
        verbose_name="Destination",
        help_text="Destination associée à cet horaire",
        null=True,
        blank=True
    )
    # Identification
    schedule_code = models.CharField(max_length=20)
    schedule_version = models.CharField(max_length=10)
    season = models.CharField(max_length=20, choices=[
        ('regular', 'Régulier'),
        ('summer', 'Été'),
        ('winter', 'Hiver'),
        ('special', 'Spécial')
    ])

    # Période
    day_of_week = models.CharField(max_length=10, choices=[
        ('monday', 'Lundi'),
        ('tuesday', 'Mardi'),
        ('wednesday', 'Mercredi'),
        ('thursday', 'Jeudi'),
        ('friday', 'Vendredi'),
        ('saturday', 'Samedi'),
        ('sunday', 'Dimanche')
    ])
    start_date = models.DateField()
    end_date = models.DateField()
    holiday_schedule = models.BooleanField(default=False)

    # Horaires
    start_time = models.TimeField()
    end_time = models.TimeField()
    frequency = models.PositiveIntegerField(help_text="Fréquence en minutes")
    rush_hour_adjustment = models.IntegerField(default=0)
    minimum_layover = models.IntegerField(default=5)

    # Ajustements
    weather_adjustment = models.JSONField(default=dict, blank=True)
    special_event_adjustment = models.JSONField(default=dict, blank=True)
    peak_hours_frequency = models.IntegerField(null=True, blank=True)
    off_peak_frequency = models.IntegerField(null=True, blank=True)

    # Nouveaux champs pour la gestion des trips
    trip_template = models.JSONField(
        default=dict,
        blank=True,
        help_text="Configuration par défaut pour la génération des trips"
    )
    schedule_metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Métriques de performance de l'horaire"
    )
    resource_requirements = models.JSONField(
        default=dict,
        blank=True,
        help_text="Exigences en ressources (véhicules, chauffeurs)"
    )

    # Statut et validation existants
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    approval_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_schedules'
    )

    # Statuts
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('pending', 'En attente de validation'),
        ('validated', 'Validé'),
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
        ('archived', 'Archivé')
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    # Gestion des versions
    is_current_version = models.BooleanField(
        default=False,
        help_text="Indique si c'est la version actuelle de l'horaire"
    )
    validation_history = models.JSONField(
        default=list,
        blank=True,
        help_text="Historique des validations"
    )
    activation_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de mise en service de l'horaire"
    )

    # Notes et métadonnées
    notes = models.TextField(blank=True)
    timepoints = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_schedules'
    )

    class Meta:
        db_table = 'transport_management_schedule'
        ordering = ['route', 'day_of_week', 'start_time']
        unique_together = [
            ('route', 'day_of_week', 'start_time', 'schedule_version'),
            ('schedule_code', 'schedule_version')
        ]
        indexes = [
            models.Index(fields=['route', 'status', 'is_active']),
            models.Index(fields=['schedule_code', 'schedule_version'])
        ]

    def generate_timepoints_for_date(self, date):
        """
        Génère les horaires pour une date spécifique en tenant compte des ajustements.
        """
        times = []
        current_datetime = datetime.combine(date, self.start_time)
        end_datetime = datetime.combine(date, self.end_time)

        frequency = self.frequency
        if self.peak_hours_frequency and self.is_peak_hour(current_datetime.time()):
            frequency = self.peak_hours_frequency
        elif self.off_peak_frequency:
            frequency = self.off_peak_frequency

        while current_datetime <= end_datetime:
            # Appliquer les ajustements météo si nécessaire
            adjusted_time = self.apply_weather_adjustment(current_datetime)
            # Appliquer les ajustements événements spéciaux
            adjusted_time = self.apply_special_event_adjustment(adjusted_time)
            
            times.append(adjusted_time.strftime('%H:%M:%S'))
            current_datetime += timedelta(minutes=frequency)
            
            if self.peak_hours_frequency and self.is_peak_hour(current_datetime.time()):
                frequency = self.peak_hours_frequency
            else:
                frequency = self.frequency

        self.timepoints = times
        self.save()

    def apply_weather_adjustment(self, datetime_obj):
        """
        Applique les ajustements météorologiques aux horaires.
        """
        if self.weather_adjustment:
            adjustment_minutes = self.weather_adjustment.get('adjustment_minutes', 0)
            return datetime_obj + timedelta(minutes=adjustment_minutes)
        return datetime_obj

    def apply_special_event_adjustment(self, datetime_obj):
        """
        Applique les ajustements pour événements spéciaux.
        """
        if self.special_event_adjustment:
            adjustment_minutes = self.special_event_adjustment.get('adjustment_minutes', 0)
            return datetime_obj + timedelta(minutes=adjustment_minutes)
        return datetime_obj

    def is_peak_hour(self, time):
        """
        Détermine si l'heure donnée est une heure de pointe.
        """
        peak_hours = [
            (datetime.strptime('07:00', '%H:%M').time(), datetime.strptime('09:00', '%H:%M').time()),
            (datetime.strptime('17:00', '%H:%M').time(), datetime.strptime('19:00', '%H:%M').time()),
        ]
        for start, end in peak_hours:
            if start <= time <= end:
                return True
        return False
    def validate_schedule(self, user, notes=''):
            """
            Valide l'horaire et met à jour l'historique de validation.
            """
            if self.status in ['validated', 'active']:
                raise ValidationError("Cet horaire est déjà validé ou actif.")

            validation_entry = {
                'validated_by': user.id,
                'validated_at': timezone.now().isoformat(),
                'version': self.schedule_version,
                'notes': notes
            }

            if isinstance(self.validation_history, list):
                self.validation_history.append(validation_entry)
            else:
                self.validation_history = [validation_entry]

            self.status = 'validated'
            self.is_approved = True
            self.approval_date = timezone.now()
            self.approved_by = user
            self.save()

    def activate(self):
        """
        Active l'horaire et désactive les versions précédentes.
        """
        if not self.is_approved:
            raise ValidationError("L'horaire doit être validé avant d'être activé.")
        
        # Désactiver les autres versions actives
        Schedule.objects.filter(
            route=self.route,
            day_of_week=self.day_of_week,
            is_current_version=True
        ).exclude(id=self.id).update(
            is_current_version=False,
            status='archived'
        )

        self.status = 'active'
        self.is_active = True
        self.activation_date = timezone.now()
        self.is_current_version = True
        self.save()

    def archive(self):
        """Archive l'horaire."""
        self.status = 'archived'
        self.is_active = False
        self.is_current_version = False
        self.save()

    def create_new_version(self):
        """Crée une nouvelle version de l'horaire."""
        new_schedule = Schedule.objects.get(pk=self.pk)
        new_schedule.pk = None
        new_schedule.schedule_version = f"v{int(self.schedule_version[1:]) + 1}" if self.schedule_version.startswith('v') else 'v2'
        new_schedule.status = 'draft'
        new_schedule.is_approved = False
        new_schedule.approval_date = None
        new_schedule.approved_by = None
        new_schedule.is_current_version = False
        new_schedule.save()
        return new_schedule

    # Nouvelles méthodes pour la gestion des trips
    def generate_trips(self, target_date):
        """Génère les trips pour une date donnée"""
        if not self.is_valid_for_date(target_date):
            return []

        # Vérifier si des trips existent déjà pour cette date
        if self.trips.filter(planned_departure__date=target_date).exists():
            return self.trips.filter(planned_departure__date=target_date)

        self.generate_timepoints_for_date(target_date)
        trips = []

        for time_point in self.timepoints:
            departure_time = datetime.combine(
                target_date,
                datetime.strptime(time_point, '%H:%M:%S').time()
            )
            arrival_time = departure_time + self.calculate_trip_duration()

            trip = Trip(
                schedule=self,
                route=self.route,
                planned_departure=departure_time,
                planned_arrival=arrival_time,
                origin=self.route.start_point.name if hasattr(self.route, 'start_point') else '',
                destination=self.route.end_point if hasattr(self.route, 'end_point') else None,
                max_capacity=self.route.vehicle_capacity if hasattr(self.route, 'vehicle_capacity') else None,
                trip_type='regular',
                priority='medium',
                status='planned',
                created_by=self.created_by
            )
            trips.append(trip)

        # Créer les trips en base de données
        Trip.objects.bulk_create(trips)
        return trips

    def calculate_trip_duration(self):
        """Calcule la durée estimée du trip"""
        # Vous pouvez ajuster cette méthode en fonction de vos besoins
        return timedelta(minutes=30)  # Par exemple, chaque trip dure 30 minutes


    def is_valid_for_date(self, target_date):
        """Vérifie si cet horaire est valide pour une date donnée"""
        return (
            self.start_date <= target_date <= self.end_date and
            self.day_of_week.lower() == target_date.strftime('%A').lower() and
            self.status == 'active'
        )

    def get_active_trips(self):
        """Récupère les trips actifs pour cet horaire"""
        return self.trips.filter(
            status__in=['scheduled', 'in_progress'],
            planned_departure__date=timezone.now().date()
        )

    def update_schedule_metrics(self):
        """Met à jour les métriques de performance"""
        today = timezone.now().date()
        daily_trips = self.trips.filter(planned_departure__date=today)
        
        metrics = {
            'date': today.isoformat(),
            'total_trips': daily_trips.count(),
            'completed_trips': daily_trips.filter(status='completed').count(),
            'on_time_trips': daily_trips.filter(schedule_adherence='on_time').count(),
            'delayed_trips': daily_trips.filter(schedule_adherence='delayed').count(),
            'cancelled_trips': daily_trips.filter(status='cancelled').count(),
            'average_delay': daily_trips.aggregate(
                Avg('delay_minutes')
            )['delay_minutes__avg'] or 0
        }

        self.schedule_metrics[today.isoformat()] = metrics
        self.save()

    def check_resource_availability(self, date):
        """Vérifie la disponibilité des ressources"""
        required_resources = self.resource_requirements.get('daily', {})
        return {
            'vehicles': self._check_vehicle_availability(date, required_resources),
            'drivers': self._check_driver_availability(date, required_resources)
        }

    def clean(self):
        """Validation des données avant sauvegarde."""
        if self.start_time >= self.end_time:
            raise ValidationError("L'heure de fin doit être après l'heure de début")
        if self.frequency <= 0:
            raise ValidationError("La fréquence doit être positive")
        if self.start_date > self.end_date:
            raise ValidationError("La date de début doit être avant la date de fin")
        if self.peak_hours_frequency and self.peak_hours_frequency < 1:
            raise ValidationError("La fréquence aux heures de pointe doit être positive")
        if self.off_peak_frequency and self.off_peak_frequency < 1:
            raise ValidationError("La fréquence hors pointe doit être positive")

    def get_next_departure(self, from_time=None):
        """Trouve le prochain départ à partir d'une heure donnée."""
        if from_time is None:
            from_time = timezone.now().time()

        if not self.timepoints:
            self.generate_timepoints_for_date(timezone.now().date())

        for timepoint in self.timepoints:
            departure_time = datetime.strptime(timepoint, '%H:%M:%S').time()
            if departure_time > from_time:
                return departure_time
        return None

    def get_validation_history(self):
        """Retourne l'historique des validations formaté."""
        return self.validation_history if isinstance(self.validation_history, list) else []

    def __str__(self):
        return f"{self.route.name} - {self.get_day_of_week_display()} ({self.start_time}-{self.end_time})"
    
    
class ScheduleException(models.Model):
    # Relations
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='exceptions')

    # Informations de base
    exception_date = models.DateField()
    exception_type = models.CharField(max_length=50, choices=[
        ('holiday', 'Jour férié'),
        ('special_event', 'Événement spécial'),
        ('weather', 'Conditions météorologiques'),
        ('maintenance', 'Maintenance'),
        ('other', 'Autre')
    ])

    # Horaires modifiés
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    modified_frequency = models.IntegerField(null=True, blank=True)

    # Statuts
    is_cancelled = models.BooleanField(default=False)
    is_modified = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=True)

    # Détails
    reason = models.TextField()
    alternative_service = models.TextField(blank=True)
    notification_sent = models.BooleanField(default=False)
    affected_routes = models.ManyToManyField('Route', blank=True)
    impact_level = models.CharField(max_length=20, choices=[
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé')
    ])

    # Métadonnées
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['exception_date']
        unique_together = ['schedule', 'exception_date']

    def __str__(self):
        return f"Exception pour {self.schedule} le {self.exception_date}"

class ResourceAvailability(models.Model):
    # Type de ressource
    resource_type = models.CharField(max_length=50, choices=[
        ('driver', 'Chauffeur'),
        ('vehicle', 'Véhicule'),
        ('maintenance_staff', 'Personnel de maintenance')
    ])
    
    # Relations
    driver = models.ForeignKey('Driver', on_delete=models.CASCADE, null=True, blank=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, null=True, blank=True)
    
    # Période de disponibilité
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    # Statut et capacité
    is_available = models.BooleanField(default=True)
    capacity_percentage = models.IntegerField(default=100)
    status = models.CharField(max_length=50, choices=[
        ('available', 'Disponible'),
        ('unavailable', 'Indisponible'),
        ('maintenance', 'En maintenance'),
        ('reserved', 'Réservé')
    ])
    
    # Restrictions et conditions
    restrictions = models.JSONField(default=list)
    conditions = models.JSONField(default=dict)
    priority_level = models.IntegerField(default=0)
    
    # Raison et commentaires
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Métadonnées
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['date', 'start_time']
        unique_together = [
            ('driver', 'date', 'start_time'),
            ('vehicle', 'date', 'start_time')
        ]
        verbose_name_plural = "Resource availabilities"

    def clean(self):
        if not self.driver and not self.vehicle:
            raise ValidationError("Either driver or vehicle must be specified")
        if self.driver and self.vehicle:
            raise ValidationError("Cannot specify both driver and vehicle")
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")

    def __str__(self):
        resource = self.driver if self.driver else self.vehicle
        return f"{self.resource_type} - {resource} on {self.date}"

class Driver(models.Model):
    # Informations personnelles
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    
    # Contact
    phone_number = models.CharField(max_length=20)
    emergency_contact = models.CharField(max_length=100)
    address = models.TextField()
    email = models.EmailField()
    
    # Qualifications
    license_number = models.CharField(max_length=50, unique=True)
    license_type = models.CharField(max_length=20, choices=[
        ('A', 'Type A'),
        ('B', 'Type B'),
        ('C', 'Type C'),
        ('D', 'Type D')
    ])
    license_expiry_date = models.DateField()
    experience_years = models.IntegerField()
    certifications = models.JSONField(default=list)
    
    # Statut et disponibilité
    employment_status = models.CharField(max_length=50, choices=[
        ('active', 'Actif'),
        ('on_leave', 'En congé'),
        ('suspended', 'Suspendu'),
        ('terminated', 'Licencié')
    ])
    availability_status = models.CharField(max_length=50, choices=[
        ('available', 'Disponible'),
        ('unavailable', 'Indisponible'),
        ('on_duty', 'En service'),
        ('on_break', 'En pause')
    ])
    
    # Performance et historique
    rating = models.DecimalField(max_digits=3, decimal_places=2)
    total_trips = models.IntegerField(default=0)
    total_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    incident_history = models.JSONField(default=list)
    performance_metrics = models.JSONField(default=dict)
    
    # Préférences et restrictions
    preferred_routes = models.ManyToManyField(Route, blank=True, related_name='preferred_drivers')
    route_restrictions = models.JSONField(default=list)
    maximum_hours_per_week = models.IntegerField(default=40)
    break_preferences = models.JSONField(default=dict)
    
    # Formation et compétences
    training_records = models.JSONField(default=list)
    special_skills = models.JSONField(default=list)
    language_skills = models.JSONField(default=list)
    
    # Métadonnées
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_medical_check = models.DateField()
    next_medical_check = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_id})"

    def is_license_valid(self):
        return timezone.now().date() < self.license_expiry_date

    def update_performance_metrics(self):
        # Logique pour mettre à jour les métriques de performance
        pass

    def check_availability(self, date, start_time, end_time):
        # Logique pour vérifier la disponibilité
        pass

class DriverSchedule(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Planifié'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
        ('pending_approval', 'En attente d\'approbation'),
        ('modified', 'Modifié')
    ]

    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('medium', 'Moyenne'),
        ('high', 'Haute'),
        ('urgent', 'Urgente')
    ]

    # Relations de base
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, help_text="Chauffeur concerné par ce planning")
    rule_set = models.ForeignKey('RuleSet', on_delete=models.SET_NULL, null=True, blank=True, 
                                help_text="Ensemble de règles appliquées à ce planning")

    # Informations temporelles
    shift_start = models.DateTimeField(default=timezone.now, help_text="Début du shift du chauffeur")
    shift_end = models.DateTimeField(default=timezone.now, help_text="Fin du shift du chauffeur")
    actual_start_time = models.DateTimeField(default=timezone.now, blank=True, 
                                           help_text="Heure réelle de début du shift")
    actual_end_time = models.DateTimeField(default=timezone.now, blank=True, 
                                         help_text="Heure réelle de fin du shift")

    # Gestion des pauses et repos
    breaks_scheduled = models.JSONField(default=dict, blank=True, 
                                      help_text="Liste des pauses programmées (ex: {'pause1': '10:30-11:00'})")
    rest_time_between_shifts = models.IntegerField(default=8, 
                                                 help_text="Temps de repos minimum entre les shifts en heures")
    
    # Statuts et contrôles
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='scheduled', 
                            help_text="Statut actuel du shift")
    is_active = models.BooleanField(default=False, help_text="Le shift est-il actif en ce moment ?")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium',
                              help_text="Priorité du planning")

    # Validation et conformité
    validation_status = models.JSONField(default=dict, help_text="État des validations des règles")
    compliance_notes = models.JSONField(default=dict, help_text="Notes de conformité aux règles")
    rule_violations = models.JSONField(default=list, help_text="Liste des violations de règles détectées")

    # Modifications et historique
    modification_history = models.JSONField(default=list, help_text="Historique des modifications")
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='driver_schedule_modifications')
    modification_reason = models.TextField(blank=True, help_text="Raison des modifications")

    # Métadonnées
    created_at = models.DateTimeField(default=timezone.now, help_text="Date de création du planning")
    updated_at = models.DateTimeField(auto_now=True, help_text="Dernière mise à jour du planning")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                 related_name='driver_schedule_creations')
    notes = models.TextField(default="", blank=True, help_text="Notes additionnelles sur ce shift")

    class Meta:
        verbose_name = "Driver Schedule"
        verbose_name_plural = "Driver Schedules"
        unique_together = ('driver', 'shift_start', 'shift_end')
        ordering = ['-shift_start', 'priority']

    def __str__(self):
        return f"Driver {self.driver} - {self.shift_start} to {self.shift_end}"

    def start_shift(self):
        """Démarre le shift et applique les règles de validation"""
        rule_check = self.validate_rules('start_shift')
        if rule_check['valid']:
            self.status = 'in_progress'
            self.is_active = True
            self.actual_start_time = timezone.now()
            self.log_modification('start_shift')
            self.save()
        return rule_check

    def end_shift(self):
        """Termine le shift et valide les règles de fin"""
        rule_check = self.validate_rules('end_shift')
        if rule_check['valid']:
            self.status = 'completed'
            self.is_active = False
            self.actual_end_time = timezone.now()
            self.log_modification('end_shift')
            self.save()
        return rule_check

    def cancel_shift(self, reason):
        """Annule le shift avec une raison"""
        self.status = 'cancelled'
        self.is_active = False
        self.modification_reason = reason
        self.log_modification('cancel_shift')
        self.save()

    def add_break(self, start_time, end_time):
        """Ajoute une pause avec validation des règles"""
        rule_check = self.validate_rules('add_break')
        if rule_check['valid']:
            break_count = len(self.breaks_scheduled) + 1
            self.breaks_scheduled[f'pause{break_count}'] = f'{start_time}-{end_time}'
            self.log_modification('add_break')
            self.save()
        return rule_check

    def validate_rules(self, action_type):
        """Valide les règles applicables pour une action donnée"""
        if self.rule_set:
            rules = self.rule_set.rules.filter(rule_type='scheduling')
            validation_results = {
                'valid': True,
                'violations': [],
                'warnings': []
            }
            for rule in rules:
                # Logique de validation des règles
                pass
            return validation_results
        return {'valid': True, 'violations': [], 'warnings': []}

    def log_modification(self, action_type):
        """Enregistre une modification dans l'historique"""
        modification = {
            'action': action_type,
            'timestamp': timezone.now().isoformat(),
            'user': self.modified_by.username if self.modified_by else 'System',
            'reason': self.modification_reason
        }
        if isinstance(self.modification_history, list):
            self.modification_history.append(modification)
        else:
            self.modification_history = [modification]

    def is_shift_overdue(self):
        """Vérifie si le shift est en retard"""
        return timezone.now() > self.shift_end and self.status != 'completed'

    def get_shift_duration(self):
        """Calcule la durée du shift"""
        if self.actual_end_time and self.actual_start_time:
            return self.actual_end_time - self.actual_start_time
        elif self.actual_start_time:
            return timezone.now() - self.actual_start_time
        return None

class DriverVehicleAssignment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('active', 'Actif'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
        ('pending_approval', 'En attente d\'approbation'),
        ('maintenance_required', 'Maintenance requise'),
        ('suspended', 'Suspendu')
    ]

    PRIORITY_LEVELS = [
        ('low', 'Basse'),
        ('medium', 'Moyenne'),
        ('high', 'Haute'),
        ('urgent', 'Urgente')
    ]

    ASSIGNMENT_TYPE = [
        ('regular', 'Régulier'),
        ('temporary', 'Temporaire'),
        ('emergency', 'Urgence'),
        ('training', 'Formation')
    ]

    # Relations principales
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, 
                             help_text="Chauffeur assigné")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, 
                              help_text="Véhicule assigné")
    rule_set = models.ForeignKey('RuleSet', on_delete=models.SET_NULL, null=True, blank=True,
                                help_text="Ensemble de règles appliquées à cette affectation")

    # Informations temporelles
    assigned_from = models.DateTimeField(default=timezone.now,
                                       help_text="Date et heure de début de l'affectation")
    assigned_until = models.DateTimeField(default=timezone.now,
                                        help_text="Date et heure de fin de l'affectation")
    actual_start = models.DateTimeField(null=True, blank=True,
                                      help_text="Date et heure réelle de début")
    actual_end = models.DateTimeField(null=True, blank=True,
                                    help_text="Date et heure réelle de fin")

    # Caractéristiques de l'affectation
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPE, 
                                     default='regular')
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, 
                              default='medium')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, 
                            default='pending')

    # Validation et conformité
    validation_status = models.JSONField(
        default=dict,
        help_text="État des validations des règles"
    )
    rule_violations = models.JSONField(
        default=list,
        help_text="Liste des violations de règles détectées"
    )
    compliance_checks = models.JSONField(
        default=dict,
        help_text="Résultats des vérifications de conformité"
    )

    # Suivi des modifications
    modification_history = models.JSONField(
        default=list,
        help_text="Historique des modifications"
    )
    modified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,
        null=True,
        related_name='vehicle_assignment_modifications'
    )
    modification_reason = models.TextField(
        blank=True,
        help_text="Raison des modifications"
    )

    # Métadonnées
    notes = models.TextField(blank=True, default="",
                           help_text="Notes additionnelles")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='vehicle_assignment_creations'
    )

    class Meta:
        verbose_name = "Driver-Vehicle Assignment"
        verbose_name_plural = "Driver-Vehicle Assignments"
        unique_together = ('driver', 'vehicle', 'assigned_from')
        ordering = ['-assigned_from', 'priority']

    def __str__(self):
        return f"{self.driver} assigned to {self.vehicle} ({self.assigned_from} to {self.assigned_until})"

    def validate_rules(self, action_type):
        """Valide les règles applicables pour une action donnée"""
        if self.rule_set:
            rules = self.rule_set.rules.filter(rule_type='assignment')
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

    def start_assignment(self):
        """Démarre l'affectation avec validation des règles"""
        rule_check = self.validate_rules('start_assignment')
        if rule_check['valid']:
            self.status = 'active'
            self.actual_start = timezone.now()
            self.log_modification('start_assignment')
            self.save()
        return rule_check

    def end_assignment(self):
        """Termine l'affectation avec validation"""
        rule_check = self.validate_rules('end_assignment')
        if rule_check['valid']:
            self.status = 'completed'
            self.actual_end = timezone.now()
            self.log_modification('end_assignment')
            self.save()
        return rule_check

    def cancel_assignment(self, reason=''):
        """Annule l'affectation avec raison"""
        self.status = 'cancelled'
        self.log_modification('cancel_assignment', reason)
        self.save()

    def suspend_assignment(self, reason=''):
        """Suspend l'affectation temporairement"""
        self.status = 'suspended'
        self.log_modification('suspend_assignment', reason)
        self.save()

    def is_active(self):
        """Vérifie si l'affectation est active"""
        now = timezone.now()
        return (self.status == 'active' and 
                self.assigned_from <= now <= self.assigned_until)

    def is_overdue(self):
        """Vérifie si l'affectation est en retard"""
        return (timezone.now() > self.assigned_until and 
                self.status not in ['completed', 'cancelled'])

    def get_duration(self):
        """Calcule la durée de l'affectation"""
        if self.actual_end and self.actual_start:
            return self.actual_end - self.actual_start
        elif self.actual_start:
            return timezone.now() - self.actual_start
        return None

    def extend_assignment(self, new_end_time):
        """Prolonge l'affectation avec validation"""
        if new_end_time <= self.assigned_until:
            raise ValueError("New end time must be later than the current end time.")
            
        rule_check = self.validate_rules('extend_assignment')
        if rule_check['valid']:
            self.assigned_until = new_end_time
            self.log_modification('extend_assignment')
            self.save()
        return rule_check

    @classmethod
    def get_current_assignment(cls, driver):
        """Récupère l'affectation active actuelle pour un chauffeur"""
        now = timezone.now()
        return cls.objects.filter(
            driver=driver,
            assigned_from__lte=now,
            assigned_until__gte=now,
            status='active'
        ).first()

    def check_vehicle_maintenance(self):
        """Vérifie si le véhicule nécessite une maintenance"""
        # Logique de vérification de la maintenance
        pass

    def validate_driver_eligibility(self):
        """Vérifie l'éligibilité du chauffeur pour ce véhicule"""
        # Logique de validation de l'éligibilité
        pass

def calculate_distance(coord1, coord2):
        
       return geodesic(coord1, coord2).kilometers

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
        null=True,
        blank=True
    )
    destination = models.ForeignKey(
        Destination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE
    )
    driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trips_as_driver'
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    rule_set = models.ForeignKey(
        RuleSet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Ensemble de règles appliquées à ce voyage"
    )

    # Informations temporelles
    trip_date = models.DateTimeField(
        default=timezone.now,
        help_text="Date et heure du voyage"
    )
    planned_departure = models.DateTimeField(
        help_text="Heure de départ prévue"
    )
    planned_arrival = models.DateTimeField(
        help_text="Heure d'arrivée prévue"
    )
    departure_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Heure de départ réelle"
    )
    arrival_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Heure d'arrivée réelle"
    )
    actual_start_time = models.DateTimeField(
        null=True,
        blank=True
    )
    actual_end_time = models.DateTimeField(
        null=True,
        blank=True
    )

    # Caractéristiques du voyage
    origin = models.CharField(
        max_length=255,
        help_text="Lieu de départ",
        null=True,
        blank=True
    )
    passenger_count = models.PositiveIntegerField(
        default=0,
        help_text="Nombre de passagers"
    )
    max_capacity = models.PositiveIntegerField(
        help_text="Capacité maximale",
        null=True,
        blank=True
    )
    trip_type = models.CharField(
        max_length=20,
        choices=TRIP_TYPE_CHOICES,
        default='regular'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )

    # Statut et suivi
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planned'
    )
    delay_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Durée du retard"
    )
    real_time_incidents = models.JSONField(
        default=list,
        help_text="Incidents survenus"
    )
    weather_conditions = models.JSONField(
        default=dict,
        help_text="Conditions météo"
    )
    traffic_conditions = models.JSONField(
        default=dict,
        help_text="Conditions de circulation"
    )

    # Validation et conformité
    validation_status = models.JSONField(
        default=dict,
        help_text="État des validations"
    )
    rule_violations = models.JSONField(
        default=list,
        help_text="Violations de règles"
    )
    safety_checks = models.JSONField(
        default=dict,
        help_text="Vérifications de sécurité"
    )

    # Suivi des modifications
    modification_history = models.JSONField(
        default=list,
        help_text="Historique des modifications"
    )
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trip_modifications'
    )
    modification_reason = models.TextField(
        blank=True
    )

    # Métadonnées
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trips_created'
    )
    notes = models.TextField(
        blank=True
    )

    class Meta:
        verbose_name = "Trip"
        verbose_name_plural = "Trips"
        ordering = ['-trip_date', 'priority']

    def __str__(self):
        return f"Trip {self.id} - {self.trip_date} - {self.route.name}"

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
            self.log_modification('end_trip')
            self.save()
        return rule_check

    def cancel_trip(self, reason=''):
        """Annule le voyage avec raison"""
        self.status = 'cancelled'
        self.log_modification('cancel_trip', reason)
        self.save()

    def add_incident(self, incident_description, severity='medium'):
        """Ajoute un incident avec plus de détails"""
        incident = {
            'description': incident_description,
            'timestamp': timezone.now().isoformat(),
            'severity': severity,
            'status': 'open'
        }
        if isinstance(self.real_time_incidents, list):
            self.real_time_incidents.append(incident)
        else:
            self.real_time_incidents = [incident]
        self.log_modification('add_incident')
        self.save()

    def increment_passenger_count(self):
        """Incrémente le nombre de passagers avec vérification de capacité"""
        if self.max_capacity is not None and self.passenger_count < self.max_capacity:
            self.passenger_count += 1
            self.log_modification('increment_passenger')
            self.save()
        else:
            raise ValueError("Capacité maximale atteinte ou non définie")

    def update_delay(self, delay_minutes):
        """Met à jour le retard du voyage"""
        self.delay_duration = timedelta(minutes=delay_minutes)
        if delay_minutes > 0:
            self.status = 'delayed'
        self.log_modification('update_delay')
        self.save()

    def get_trip_duration(self):
        """Calcule la durée du voyage"""
        if self.actual_end_time and self.actual_start_time:
            return self.actual_end_time - self.actual_start_time
        return None

    def check_safety_requirements(self):
        """Vérifie les exigences de sécurité"""
        # Logique de vérification de sécurité
        pass
    

    
    def update_status(self):
        """Met à jour le statut du voyage en fonction du temps et de la position."""
        now = timezone.now()
        time_to_departure = (self.planned_departure - now).total_seconds() / 60  # en minutes
        time_since_departure = (now - self.planned_departure).total_seconds() / 60  # en minutes
        time_to_arrival = (self.planned_arrival - now).total_seconds() / 60  # en minutes

        # Récupérer la dernière position du bus
        bus_position = BusPosition.objects.filter(trip=self).order_by('-timestamp').first()

        # Par défaut, statut initial
        new_status = 'scheduled'

        if time_to_departure > 10:
            new_status = 'scheduled'
        elif 5 < time_to_departure <= 10:
            new_status = 'boarding_soon'
        elif 0 <= time_to_departure <= 5:
            new_status = 'boarding'
        elif time_since_departure >= 0 and time_to_arrival > 5:
            new_status = 'in_transit'
        elif bus_position and self.destination and \
             self.destination.latitude is not None and self.destination.longitude is not None:
            # Calculer la distance jusqu'à la destination
            try:
                destination_coords = (self.destination.latitude, self.destination.longitude)
                bus_coords = (bus_position.latitude, bus_position.longitude)
                distance_to_destination = calculate_distance(bus_coords, destination_coords)
                if distance_to_destination <= 1:  # Moins de 1 km
                    new_status = 'arriving_soon'
                else:
                    new_status = 'in_transit'
            except Exception as e:
                # Gérer les erreurs potentielles lors du calcul de distance
                new_status = 'in_transit'
        elif 0 <= time_to_arrival <= 5:
            new_status = 'arriving_soon'
        elif time_since_departure > 0 and time_to_arrival <= 0:
            new_status = 'completed'
        else:
            new_status = 'scheduled'  # Statut par défaut si aucune condition n'est remplie

        # Mettre à jour le statut du trip si différent
        if self.status != new_status:
            self.status = new_status
            self.save()

        # Mettre à jour le statut du trip

        # Envoyer la mise à jour via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'trip_status_{self.id}',
            {
                'type': 'send_status',
                'status': {
                    'trip_id': self.id,
                    'status': self.status
                }
            }
        )
    


    def update_weather_conditions(self, conditions):
        """Met à jour les conditions météo"""
        self.weather_conditions.update(conditions)
        self.save()


class PassengerTrip(models.Model):
    BOARDING_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('checked_in', 'Enregistré'),
        ('boarded', 'À Bord'),
        ('boarding_failed', 'Échec Embarquement'),
        ('off_board', 'Descendu'),
        ('no_show', 'Non présenté'),
        ('cancelled', 'Annulé')
    ]

    PASSENGER_TYPE_CHOICES = [
        ('regular', 'Régulier'),
        ('student', 'Étudiant'),
        ('senior', 'Senior'),
        ('disabled', 'PMR'),
        ('child', 'Enfant'),
        ('vip', 'VIP')
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('paid', 'Payé'),
        ('refunded', 'Remboursé'),
        ('failed', 'Échoué')
    ]

    # Relations principales
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, 
                           help_text="Lien vers le trajet concerné")
    passenger = models.ForeignKey(User, on_delete=models.CASCADE, 
                                help_text="Le passager lié à ce voyage")
    boarding_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, 
                                    related_name='boarding_trips')
    alighting_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, 
                                     related_name='alighting_trips', 
                                     null=True, blank=True)
    rule_set = models.ForeignKey('RuleSet', on_delete=models.SET_NULL, 
                                null=True, blank=True,
                                help_text="Règles appliquées à ce voyage passager")

    # Informations temporelles
    boarding_time = models.DateTimeField(null=True, blank=True)
    departure_time = models.DateTimeField(null=True, blank=True)
    arrival_time = models.DateTimeField(null=True, blank=True)
    check_in_time = models.DateTimeField(null=True, blank=True)

    # Statuts
    status = models.CharField(max_length=20, default='pending')
    boarding_status = models.CharField(max_length=50, 
                                     choices=BOARDING_STATUS_CHOICES, 
                                     default='pending')
    passenger_type = models.CharField(max_length=20, 
                                    choices=PASSENGER_TYPE_CHOICES, 
                                    default='regular')
    payment_status = models.CharField(max_length=20, 
                                    choices=PAYMENT_STATUS_CHOICES, 
                                    default='pending')

    # Informations de voyage
    seat_number = models.CharField(max_length=10, blank=True, default="")
    special_needs = models.JSONField(default=dict, 
                                   help_text="Besoins spéciaux détaillés")
    luggage_info = models.JSONField(default=dict, 
                                  help_text="Informations sur les bagages")
    fare_paid = models.DecimalField(max_digits=10, decimal_places=2, 
                                  default=0.00)
    ticket_number = models.CharField(max_length=50, unique=True, null=True)

    # Validation et conformité
    validation_status = models.JSONField(default=dict)
    rule_violations = models.JSONField(default=list)
    boarding_failure_reason = models.TextField(blank=True, default="")

    # Retour d'expérience
    feedback = models.JSONField(default=dict)
    satisfaction_rating = models.IntegerField(null=True, blank=True)
    incident_reports = models.JSONField(default=list)

    # Historique et modifications
    modification_history = models.JSONField(default=list)
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                  null=True, 
                                  related_name='passenger_trip_modifications')
    
    # Métadonnées
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                 null=True, 
                                 related_name='passenger_trips_created')
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Passenger Trip"
        verbose_name_plural = "Passenger Trips"
        unique_together = ('trip', 'passenger')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.passenger.username} on Trip {self.trip.id}"

    def validate_rules(self, action_type):
        """Valide les règles applicables"""
        if self.rule_set:
            rules = self.rule_set.rules.filter(rule_type='passenger_trip')
            validation_results = {
                'valid': True,
                'violations': [],
                'warnings': []
            }
            return validation_results
        return {'valid': True, 'violations': [], 'warnings': []}

    def log_modification(self, action_type, reason=''):
        """Enregistre une modification"""
        modification = {
            'action': action_type,
            'timestamp': timezone.now().isoformat(),
            'user': self.modified_by.username if self.modified_by else 'System',
            'reason': reason
        }
        if isinstance(self.modification_history, list):
            self.modification_history.append(modification)
        else:
            self.modification_history = [modification]

    def check_in(self):
        """Enregistre le passager"""
        rule_check = self.validate_rules('check_in')
        if rule_check['valid']:
            self.boarding_status = 'checked_in'
            self.check_in_time = timezone.now()
            self.log_modification('check_in')
            self.save()
        return rule_check

    def board_passenger(self):
        """Embarque le passager"""
        rule_check = self.validate_rules('board')
        if rule_check['valid']:
            self.boarding_status = 'boarded'
            self.boarding_time = timezone.now()
            self.log_modification('board')
            self.save()
        return rule_check

    def fail_boarding(self, reason):
        """Enregistre un échec d'embarquement"""
        self.boarding_status = 'boarding_failed'
        self.boarding_failure_reason = reason
        self.log_modification('boarding_failed', reason)
        self.save()

    def disembark_passenger(self):
        """Débarque le passager"""
        rule_check = self.validate_rules('disembark')
        if rule_check['valid']:
            self.boarding_status = 'off_board'
            self.arrival_time = timezone.now()
            self.log_modification('disembark')
            self.save()
        return rule_check

    def mark_no_show(self, reason=''):
        """Marque le passager comme non présent"""
        self.boarding_status = 'no_show'
        self.log_modification('no_show', reason)
        self.save()

    def add_feedback(self, feedback_data):
        """Ajoute un retour d'expérience structuré"""
        self.feedback = {
            'timestamp': timezone.now().isoformat(),
            'content': feedback_data,
            'submitted_by': self.passenger.username
        }
        self.log_modification('add_feedback')
        self.save()

    def report_incident(self, incident_data):
        """Enregistre un incident"""
        incident = {
            'timestamp': timezone.now().isoformat(),
            'details': incident_data,
            'status': 'reported'
        }
        if isinstance(self.incident_reports, list):
            self.incident_reports.append(incident)
        else:
            self.incident_reports = [incident]
        self.log_modification('report_incident')
        self.save()

    def get_trip_duration(self):
        """Calcule la durée du voyage"""
        if self.arrival_time and self.departure_time:
            return self.arrival_time - self.departure_time
        return None

    def is_trip_completed(self):
        """Vérifie si le voyage est terminé"""
        return self.boarding_status == 'off_board' and self.arrival_time is not None

    @classmethod
    def get_active_trips_for_passenger(cls, passenger):
        """Récupère les voyages actifs d'un passager"""
        return cls.objects.filter(
            passenger=passenger, 
            boarding_status='boarded'
        )

    @classmethod
    def get_trip_history_for_passenger(cls, passenger):
        """Récupère l'historique des voyages d'un passager"""
        return cls.objects.filter(passenger=passenger).order_by('-created_at')


class Incident(models.Model):
    INCIDENT_TYPE_CHOICES = [
        ('accident', 'Accident'),
        ('delay', 'Retard'),
        ('mechanical_failure', 'Panne mécanique'),
        ('passenger_complaint', 'Plainte passager'),
        ('security', 'Incident de sécurité'),
        ('medical', 'Urgence médicale'),
        ('weather_related', 'Lié à la météo'),
        ('traffic', 'Incident de circulation'),
        ('staff', 'Incident lié au personnel'),
        ('other', 'Autre'),
    ]

    SEVERITY_LEVELS = [
        ('minor', 'Mineur'),
        ('moderate', 'Modéré'),
        ('major', 'Majeur'),
        ('critical', 'Critique'),
        ('emergency', 'Urgence')
    ]

    PRIORITY_LEVELS = [
        ('low', 'Basse'),
        ('medium', 'Moyenne'),
        ('high', 'Haute'),
        ('urgent', 'Urgente')
    ]

    # Relations principales
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='incidents')
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='reported_incidents')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='assigned_incidents')
    rule_set = models.ForeignKey('RuleSet', on_delete=models.SET_NULL, null=True, 
                                help_text="Règles de gestion des incidents")

    # Informations de base
    incident_id = models.CharField(max_length=50, unique=True)
    type = models.CharField(max_length=50, choices=INCIDENT_TYPE_CHOICES, default='other')
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='minor')
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='medium')
    date = models.DateTimeField(default=timezone.now)
    location = models.JSONField(default=dict, help_text="Localisation détaillée de l'incident")

    # Description et détails
    description = models.TextField()
    detailed_report = models.JSONField(default=dict)
    affected_assets = models.JSONField(default=list)
    witnesses = models.JSONField(default=list)
    evidence = models.JSONField(default=list)

    # Statut et résolution
    status = models.CharField(max_length=50, choices=[
        ('reported', 'Signalé'),
        ('under_investigation', 'En cours d\'investigation'),
        ('action_required', 'Action requise'),
        ('in_progress', 'En cours de résolution'),
        ('resolved', 'Résolu'),
        ('closed', 'Clôturé'),
        ('reopened', 'Réouvert')
    ], default='reported')
    
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_details = models.JSONField(default=dict)
    resolution_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Suivi et validation
    validation_status = models.JSONField(default=dict)
    rule_violations = models.JSONField(default=list)
    follow_up_actions = models.JSONField(default=list)
    preventive_measures = models.JSONField(default=list)

    # Historique et modifications
    modification_history = models.JSONField(default=list)
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='incident_modifications')

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                 related_name='incidents_created')

    class Meta:
        verbose_name = "Incident"
        verbose_name_plural = "Incidents"
        ordering = ['-date', 'priority']

    def __str__(self):
        return f"Incident {self.incident_id} - {self.get_type_display()} ({self.date})"

    def generate_incident_id(self):
        """Génère un ID unique pour l'incident"""
        prefix = self.type[:3].upper()
        timestamp = timezone.now().strftime('%Y%m%d%H%M')
        return f"{prefix}-{timestamp}-{str(self.id).zfill(4)}"

    def save(self, *args, **kwargs):
        if not self.incident_id:
            super().save(*args, **kwargs)
            self.incident_id = self.generate_incident_id()
        super().save(*args, **kwargs)

    def validate_rules(self, action_type):
        """Valide les règles applicables"""
        if self.rule_set:
            rules = self.rule_set.rules.filter(rule_type='incident')
            validation_results = {
                'valid': True,
                'violations': [],
                'warnings': []
            }
            return validation_results
        return {'valid': True, 'violations': [], 'warnings': []}

    def log_modification(self, action_type, reason=''):
        """Enregistre une modification"""
        modification = {
            'action': action_type,
            'timestamp': timezone.now().isoformat(),
            'user': self.modified_by.username if self.modified_by else 'System',
            'reason': reason
        }
        if isinstance(self.modification_history, list):
            self.modification_history.append(modification)
        else:
            self.modification_history = [modification]

    def mark_as_resolved(self, resolution_details, cost=None):
        """Marque l'incident comme résolu avec détails"""
        rule_check = self.validate_rules('resolve')
        if rule_check['valid']:
            self.resolved = True
            self.resolved_at = timezone.now()
            self.status = 'resolved'
            self.resolution_details = {
                'details': resolution_details,
                'resolved_at': timezone.now().isoformat(),
                'resolved_by': self.modified_by.username if self.modified_by else 'System'
            }
            if cost:
                self.resolution_cost = cost
            self.log_modification('resolve')
            self.save()
        return rule_check

    def escalate(self, reason):
        """Escalade l'incident"""
        self.priority = 'urgent'
        self.log_modification('escalate', reason)
        self.save()

    def add_follow_up_action(self, action):
        """Ajoute une action de suivi"""
        follow_up = {
            'action': action,
            'timestamp': timezone.now().isoformat(),
            'status': 'pending'
        }
        if isinstance(self.follow_up_actions, list):
            self.follow_up_actions.append(follow_up)
        else:
            self.follow_up_actions = [follow_up]
        self.save()

    def add_preventive_measure(self, measure):
        """Ajoute une mesure préventive"""
        preventive = {
            'measure': measure,
            'added_at': timezone.now().isoformat(),
            'status': 'proposed'
        }
        if isinstance(self.preventive_measures, list):
            self.preventive_measures.append(preventive)
        else:
            self.preventive_measures = [preventive]
        self.save()

    def get_incident_duration(self):
        """Calcule la durée de l'incident"""
        if self.resolved_at:
            return self.resolved_at - self.date
        return timezone.now() - self.date

    @classmethod
    def get_active_incidents(cls):
        """Récupère tous les incidents actifs"""
        return cls.objects.filter(resolved=False).order_by('priority', '-date')

    @classmethod
    def get_incidents_by_type(cls, incident_type):
        """Récupère les incidents par type"""
        return cls.objects.filter(type=incident_type).order_by('-date')

class EventLog(models.Model):
    EVENT_TYPE_CHOICES = [
        ('trip_start', 'Départ du voyage'),
        ('trip_end', 'Fin du voyage'),
        ('passenger_boarding', 'Embarquement passager'),
        ('passenger_alighting', 'Débarquement passager'),
        ('delay', 'Retard'),
        ('incident', 'Incident'),
        ('route_deviation', 'Déviation de route'),
        ('vehicle_status', 'Statut du véhicule'),
        ('driver_status', 'Statut du chauffeur'),
        ('safety_check', 'Vérification de sécurité'),
        ('maintenance_alert', 'Alerte maintenance'),
        ('weather_alert', 'Alerte météo'),
        ('system_alert', 'Alerte système'),
        ('rule_violation', 'Violation de règle'),
        ('schedule_change', 'Changement d\'horaire')
    ]

    SEVERITY_LEVELS = [
        ('info', 'Information'),
        ('warning', 'Avertissement'),
        ('error', 'Erreur'),
        ('critical', 'Critique')
    ]

    # Relations principales
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, 
                           related_name='event_logs')
    rule_set = models.ForeignKey('RuleSet', on_delete=models.SET_NULL, 
                                null=True, blank=True,
                                help_text="Règles associées à l'événement")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                 null=True, 
                                 related_name='created_events')

    # Informations de base
    event_id = models.CharField(max_length=50, unique=True)
    event_type = models.CharField(max_length=100, choices=EVENT_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, 
                              default='info')
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.TextField()

    # Détails de l'événement
    event_data = models.JSONField(default=dict, 
                                help_text="Données détaillées de l'événement")
    location_data = models.JSONField(default=dict, 
                                   help_text="Données de localisation")
    related_entities = models.JSONField(default=dict, 
                                      help_text="Entités liées à l'événement")
    context_data = models.JSONField(default=dict, 
                                  help_text="Données contextuelles")

    # Traitement et suivi
    processed = models.BooleanField(default=False)
    processing_status = models.CharField(max_length=50, choices=[
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('processed', 'Traité'),
        ('failed', 'Échec'),
        ('ignored', 'Ignoré')
    ], default='pending')
    processing_details = models.JSONField(default=dict)
    requires_action = models.BooleanField(default=False)
    action_taken = models.JSONField(default=dict)

    # Validation et conformité
    validation_status = models.JSONField(default=dict)
    rule_violations = models.JSONField(default=list)

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source = models.CharField(max_length=100, help_text="Source de l'événement")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        verbose_name = "Event Log"
        verbose_name_plural = "Event Logs"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['trip', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.trip} - {self.timestamp}"

    def save(self, *args, **kwargs):
        if not self.event_id:
            # Génère un ID unique pour l'événement
            prefix = self.event_type[:3].upper()
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.event_id = f"{prefix}-{timestamp}-{uuid.uuid4().hex[:6]}"
        
        # Validation automatique si un rule_set est défini
        if self.rule_set and not self.validation_status:
            self.validate_event()
            
        super().save(*args, **kwargs)

    def validate_event(self):
        """Valide l'événement selon les règles définies"""
        if self.rule_set:
            rules = self.rule_set.rules.filter(rule_type='event')
            validation_results = {
                'timestamp': timezone.now().isoformat(),
                'valid': True,
                'violations': [],
                'warnings': []
            }
            self.validation_status = validation_results

    def mark_as_processed(self, details=None):
        """Marque l'événement comme traité"""
        self.processed = True
        self.processing_status = 'processed'
        if details:
            self.processing_details.update({
                'processed_at': timezone.now().isoformat(),
                'details': details
            })
        self.save()

    def add_action(self, action_details):
        """Ajoute une action prise en réponse à l'événement"""
        action = {
            'timestamp': timezone.now().isoformat(),
            'details': action_details,
            'user': self.created_by.username if self.created_by else 'System'
        }
        if isinstance(self.action_taken, dict):
            self.action_taken['actions'] = self.action_taken.get('actions', []) + [action]
        else:
            self.action_taken = {'actions': [action]}
        self.save()

    def add_context(self, context_key, context_value):
        """Ajoute des données contextuelles à l'événement"""
        if isinstance(self.context_data, dict):
            self.context_data[context_key] = context_value
            self.save()

    def update_location(self, latitude, longitude, additional_info=None):
        """Met à jour les informations de localisation"""
        location_data = {
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timezone.now().isoformat()
        }
        if additional_info:
            location_data.update(additional_info)
        self.location_data = location_data
        self.save()

    @classmethod
    def log_event(cls, trip, event_type, description, **kwargs):
        """Méthode de classe pour créer un nouvel événement"""
        return cls.objects.create(
            trip=trip,
            event_type=event_type,
            description=description,
            **kwargs
        )

    @classmethod
    def get_events_for_trip(cls, trip, start_date=None, end_date=None):
        """Récupère les événements pour un voyage donné"""
        queryset = cls.objects.filter(trip=trip)
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        return queryset.order_by('timestamp')

    @classmethod
    def get_events_by_type(cls, event_type, start_date=None, end_date=None):
        """Récupère les événements par type"""
        queryset = cls.objects.filter(event_type=event_type)
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        return queryset.order_by('timestamp')


class TripStatus(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Planifié'),
        ('preparing', 'En préparation'),
        ('ongoing', 'En cours'),
        ('delayed', 'Retardé'),
        ('paused', 'En pause'),
        ('completed', 'Terminé'),
        ('canceled', 'Annulé'),
        ('interrupted', 'Interrompu')
    ]

    COMPLETION_STAGES = [
        ('not_started', 'Non commencé'),
        ('initial_checks', 'Vérifications initiales'),
        ('in_progress', 'En progression'),
        ('final_checks', 'Vérifications finales'),
        ('completed', 'Terminé')
    ]

    # Identifiants et relations principales
    trip_status_id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, 
                           help_text="Trajet concerné")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, 
                              help_text="Véhicule affecté")
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, 
                             help_text="Chauffeur assigné")
    rule_set = models.ForeignKey('RuleSet', on_delete=models.SET_NULL, 
                                null=True, blank=True,
                                help_text="Règles appliquées au statut")

    # Statut général
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, 
                            default='scheduled')
    stage = models.CharField(max_length=50, choices=COMPLETION_STAGES, 
                           default='not_started')
    progress_percentage = models.IntegerField(default=0, 
                                            validators=[MinValueValidator(0), 
                                                      MaxValueValidator(100)])

    # Suivi des arrêts et pauses
    breaks_status = models.JSONField(default=dict, help_text="Statut détaillé des pauses")
    breaks_completed = models.BooleanField(default=False)
    stops_status = models.JSONField(default=dict, help_text="Statut détaillé des arrêts")
    stops_completed = models.BooleanField(default=False)
    next_stop = models.ForeignKey('Stop', on_delete=models.SET_NULL, 
                                 null=True, blank=True,
                                 related_name='next_stops')

    # Suivi des incidents
    incidents_status = models.JSONField(default=dict)
    incidents_resolved = models.BooleanField(default=False)
    active_incidents = models.JSONField(default=list)

    # Métriques de performance
    delay_duration = models.DurationField(null=True, blank=True)
    estimated_completion_time = models.DateTimeField(null=True, blank=True)
    performance_metrics = models.JSONField(default=dict)

    # Validation et conformité
    validation_status = models.JSONField(default=dict)
    rule_violations = models.JSONField(default=list)
    safety_checks = models.JSONField(default=dict)

    # Suivi des modifications
    modification_history = models.JSONField(default=list)
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                  null=True, related_name='status_modifications')

    # Métadonnées
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trip Status"
        verbose_name_plural = "Trip Statuses"
        ordering = ['-updated_at']

    def __str__(self):
        return f"Status {self.trip_status_id} - {self.status} - Trip {self.trip.id}"

    def validate_rules(self, action_type):
        """Valide les règles applicables"""
        if self.rule_set:
            rules = self.rule_set.rules.filter(rule_type='trip_status')
            validation_results = {
                'valid': True,
                'violations': [],
                'warnings': []
            }
            return validation_results
        return {'valid': True, 'violations': [], 'warnings': []}

    def log_modification(self, action_type, reason=''):
        """Enregistre une modification"""
        modification = {
            'action': action_type,
            'timestamp': timezone.now().isoformat(),
            'user': self.modified_by.username if self.modified_by else 'System',
            'reason': reason
        }
        if isinstance(self.modification_history, list):
            self.modification_history.append(modification)
        else:
            self.modification_history = [modification]

    def update_status(self, new_status, reason=''):
        """Met à jour le statut avec validation"""
        rule_check = self.validate_rules('update_status')
        if rule_check['valid']:
            self.status = new_status
            self.log_modification('status_update', reason)
            self.save()
        return rule_check

    def update_progress(self):
        """Met à jour la progression globale"""
        total_stops = len(self.stops_status)
        completed_stops = len([s for s in self.stops_status.values() if s.get('completed')])
        self.progress_percentage = (completed_stops / total_stops * 100) if total_stops > 0 else 0
        self.save()

    def record_break(self, break_id, status):
        """Enregistre le statut d'une pause"""
        if isinstance(self.breaks_status, dict):
            self.breaks_status[break_id] = {
                'status': status,
                'timestamp': timezone.now().isoformat()
            }
            self.breaks_completed = all(b.get('status') == 'completed' 
                                      for b in self.breaks_status.values())
            self.save()

    def record_stop(self, stop_id, status):
        """Enregistre le statut d'un arrêt"""
        if isinstance(self.stops_status, dict):
            self.stops_status[stop_id] = {
                'status': status,
                'timestamp': timezone.now().isoformat()
            }
            self.stops_completed = all(s.get('status') == 'completed' 
                                     for s in self.stops_status.values())
            self.update_progress()
            self.save()

    def record_incident(self, incident_data):
        """Enregistre un nouvel incident"""
        incident = {
            'timestamp': timezone.now().isoformat(),
            'details': incident_data,
            'status': 'active'
        }
        if isinstance(self.active_incidents, list):
            self.active_incidents.append(incident)
        else:
            self.active_incidents = [incident]
        self.save()

    def resolve_incident(self, incident_id, resolution_details):
        """Résout un incident actif"""
        if isinstance(self.active_incidents, list):
            for incident in self.active_incidents:
                if incident.get('id') == incident_id:
                    incident['status'] = 'resolved'
                    incident['resolution'] = {
                        'details': resolution_details,
                        'timestamp': timezone.now().isoformat()
                    }
            self.active_incidents = [i for i in self.active_incidents 
                                   if i.get('status') == 'active']
            self.incidents_resolved = len(self.active_incidents) == 0
            self.save()

    def update_safety_checks(self, check_data):
        """Met à jour les vérifications de sécurité"""
        if isinstance(self.safety_checks, dict):
            self.safety_checks.update({
                timezone.now().isoformat(): check_data
            })
            self.save()

    def calculate_delay(self):
        """Calcule le retard actuel"""
        if hasattr(self.trip, 'planned_arrival'):
            estimated_arrival = timezone.now() + self.estimate_remaining_time()
            if estimated_arrival > self.trip.planned_arrival:
                self.delay_duration = estimated_arrival - self.trip.planned_arrival
                self.save()

    def estimate_remaining_time(self):
        """Estime le temps restant"""
        # Logique d'estimation du temps restant
        pass

    @classmethod
    def get_active_statuses(cls):
        """Récupère tous les statuts actifs"""
        return cls.objects.filter(status__in=['ongoing', 'delayed', 'paused'])

    @classmethod
    def get_delayed_trips(cls):
        """Récupère les trajets en retard"""
        return cls.objects.filter(status='delayed')

class DisplaySchedule(models.Model):
    STATUS_CHOICES = [
        ('on_time', 'À l\'heure'),
        ('approaching', 'En approche'),
        ('boarding', 'Embarquement'),
        ('delayed', 'Retardé'),
        ('departed', 'Parti'),
        ('canceled', 'Annulé'),
        ('diverted', 'Dévié')
    ]

    DISPLAY_PRIORITY = [
        ('normal', 'Normal'),
        ('important', 'Important'),
        ('urgent', 'Urgent'),
        ('low', 'Faible')
    ]

    # Identifiants et relations principales
    display_schedule_id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(Trip, on_delete=models.SET_NULL, null=True,
                           help_text="Voyage associé")
    rule_set = models.ForeignKey(RuleSet, on_delete=models.SET_NULL, 
                                null=True, blank=True,
                                help_text="Règles d'affichage")

    # Informations d'affichage de base
    bus_number = models.CharField(max_length=50, 
                                help_text="Numéro du bus")
    display_order = models.IntegerField(default=0,
                                      help_text="Ordre d'affichage")
    display_priority = models.CharField(max_length=20, 
                                      choices=DISPLAY_PRIORITY,
                                      default='normal')

    # Horaires et timing
    scheduled_departure = models.DateTimeField(
        help_text="Heure de départ prévue")
    estimated_departure = models.DateTimeField(
        null=True, blank=True,
        help_text="Heure de départ estimée")
    scheduled_arrival = models.DateTimeField(
        help_text="Heure d'arrivée prévue")
    estimated_arrival = models.DateTimeField(
        null=True, blank=True,
        help_text="Heure d'arrivée estimée")
    
    # Informations sur l'emplacement
    gate_number = models.CharField(max_length=50,
                                 help_text="Numéro de la porte")
    platform = models.CharField(max_length=50,
                              help_text="Numéro du quai",
                              blank=True)
    terminal = models.CharField(max_length=50,
                              help_text="Terminal",
                              blank=True)

    # Capacité et disponibilité
    seats_available = models.IntegerField(
        default=0,
        help_text="Nombre de places disponibles")
    seats_reserved = models.IntegerField(
        default=0,
        help_text="Nombre de places réservées")
    
    # Localisation et suivi
    current_location = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Localisation actuelle")
    location_coordinates = models.JSONField(
        default=dict,
        help_text="Coordonnées GPS actuelles")
    next_stop = models.ForeignKey(
        Stop, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='next_displayed_stops')

    # Statut et notifications
    status = models.CharField(
        max_length=50, 
        choices=STATUS_CHOICES,
        default='on_time')
    delay_duration = models.DurationField(null=True, blank=True)
    status_message = models.CharField(max_length=255, blank=True)
    announcements = models.JSONField(default=list)

    # Validation et suivi
    validation_status = models.JSONField(default=dict)
    display_rules = models.JSONField(default=dict)
    display_history = models.JSONField(default=list)

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_refresh = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,
        null=True,
        related_name='schedule_display_modifications')

    class Meta:
        verbose_name = "Display Schedule"
        verbose_name_plural = "Display Schedules"
        ordering = ['display_order', 'scheduled_departure']

    def __str__(self):
        if self.trip:
            return f"Display for Trip {self.trip.id} - {self.trip.route.name} - {self.scheduled_departure}"
        return f"Display {self.display_schedule_id} - {self.scheduled_departure}"

    # Propriétés pour l'accès aux informations via Trip
    @property
    def route(self):
        """Accède à la route via le voyage"""
        return self.trip.route if self.trip else None

    @property
    def origin(self):
        """Accède à l'origine via le voyage"""
        return self.trip.origin if self.trip else None

    @property
    def destination(self):
        """Accède à la destination via le voyage"""
        return self.trip.destination if self.trip else None

    @property
    def trip_vehicle(self):
        """Accède au véhicule via le voyage"""
        return self.trip.vehicle if self.trip else None

    @property
    def trip_driver(self):
        """Accède au chauffeur via le voyage"""
        return self.trip.driver if self.trip else None

    @property
    def total_seats(self):
        """Calcule le nombre total de places"""
        return self.trip.max_capacity if self.trip else 0

    def validate_rules(self):
        """Valide les règles d'affichage"""
        if self.rule_set:
            rules = self.rule_set.rules.filter(rule_type='display')
            validation_results = {
                'valid': True,
                'violations': [],
                'warnings': []
            }
            return validation_results
        return {'valid': True, 'violations': [], 'warnings': []}

    def update_status(self, new_status, message=None):
        """Met à jour le statut d'affichage"""
        self.status = new_status
        if message:
            self.status_message = message
        self.log_display_change('status_update')
        self.save()

    def log_display_change(self, change_type):
        """Enregistre un changement d'affichage"""
        change = {
            'type': change_type,
            'timestamp': timezone.now().isoformat(),
            'user': self.modified_by.username if self.modified_by else 'System',
            'status': self.status,
            'message': self.status_message
        }
        if isinstance(self.display_history, list):
            self.display_history.append(change)
        else:
            self.display_history = [change]

    def add_announcement(self, message, priority='normal'):
        """Ajoute une annonce à afficher"""
        announcement = {
            'message': message,
            'priority': priority,
            'timestamp': timezone.now().isoformat()
        }
        if isinstance(self.announcements, list):
            self.announcements.append(announcement)
        else:
            self.announcements = [announcement]
        self.save()

    def update_location(self, latitude, longitude):
        """Met à jour la position actuelle"""
        self.location_coordinates = {
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timezone.now().isoformat()
        }
        self.save()

    def calculate_delay(self):
        """Calcule le retard actuel"""
        if self.estimated_departure and self.scheduled_departure:
            self.delay_duration = self.estimated_departure - self.scheduled_departure
            if self.delay_duration.total_seconds() > 0:
                self.status = 'delayed'
            self.save()

    def update_seats(self, available, reserved=None):
        """Met à jour la disponibilité des places"""
        self.seats_available = min(available, self.total_seats)
        if reserved is not None:
            self.seats_reserved = min(reserved, self.total_seats - self.seats_available)
        self.save()

    def refresh_display(self):
        """Rafraîchit les informations d'affichage"""
        if self.trip:
            self.calculate_delay()
            self.validate_rules()
            self.last_refresh = timezone.now()
            self.save()

    def sync_with_trip(self):
        """Synchronise les informations avec le voyage associé"""
        if self.trip:
            self.scheduled_departure = self.trip.planned_departure
            self.scheduled_arrival = self.trip.planned_arrival
            self.seats_available = self.trip.max_capacity - self.trip.passenger_count
            self.calculate_delay()
            self.save()

    @classmethod
    def get_active_displays(cls):
        """Récupère les affichages actifs"""
        return cls.objects.filter(
            scheduled_departure__gte=timezone.now()
        ).order_by('display_order', 'scheduled_departure')

    @classmethod
    def get_delayed_schedules(cls):
        """Récupère les horaires en retard"""
        return cls.objects.filter(status='delayed')

    @classmethod
    def cleanup_old_displays(cls):
        """Nettoie les anciens affichages"""
        threshold = timezone.now() - timezone.timedelta(hours=24)
        cls.objects.filter(scheduled_departure__lt=threshold).delete()
        
        
class BusPosition(models.Model):
    POSITION_STATUS_CHOICES = [
        ('active', 'Active'),
        ('invalid', 'Invalid'),
        ('interpolated', 'Interpolated'),
        ('predicted', 'Predicted')
    ]

    # Identifiant et relations principales
    position_id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(Trip, 
                           on_delete=models.CASCADE,
                           related_name='positions',
                           help_text="Voyage associé à cette position")
    rule_set = models.ForeignKey(RuleSet, 
                                on_delete=models.SET_NULL,
                                null=True, blank=True,
                                help_text="Règles de validation de position")

    # Coordonnées GPS
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        help_text="Latitude en temps réel")
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        help_text="Longitude en temps réel")
    altitude = models.DecimalField(
        max_digits=7, 
        decimal_places=2,
        null=True, blank=True,
        help_text="Altitude en mètres")

    # Informations de mouvement
    speed = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        help_text="Vitesse en km/h")
    heading = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        null=True, blank=True,
        help_text="Direction en degrés")
    is_moving = models.BooleanField(
        default=False,
        help_text="Statut de mouvement")

    # Qualité et statut
    position_status = models.CharField(
        max_length=20,
        choices=POSITION_STATUS_CHOICES,
        default='active',
        help_text="Statut de la position")
    accuracy = models.FloatField(
        null=True, blank=True,
        help_text="Précision en mètres")
    hdop = models.FloatField(
        null=True, blank=True,
        help_text="Dilution horizontale de la précision")

    # Horodatage et validité
    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="Horodatage de la position")
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date d'enregistrement")
    is_valid = models.BooleanField(
        default=True,
        help_text="Validité de la position")

    # Métadonnées
    data_source = models.CharField(
        max_length=50,
        default='gps',
        help_text="Source des données de position")
    raw_data = models.JSONField(
        default=dict,
        help_text="Données brutes du GPS")

    class Meta:
        verbose_name = "Bus Position"
        verbose_name_plural = "Bus Positions"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['trip', '-timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"Position for Trip {self.trip.id} at {self.timestamp}"

    @property
    def vehicle(self):
        """Accède au véhicule via le voyage"""
        return self.trip.vehicle if self.trip else None

    def validate_position(self):
        """Valide la position selon les règles définies"""
        if self.rule_set:
            rules = self.rule_set.rules.filter(rule_type='position')
            # Logique de validation
            pass
        return True

    def calculate_distance_from_previous(self):
        """Calcule la distance depuis la dernière position"""
        previous = BusPosition.objects.filter(
            trip=self.trip,
            timestamp__lt=self.timestamp
        ).order_by('-timestamp').first()

        if previous:
            from math import radians, sin, cos, sqrt, atan2
            
            lat1, lon1 = radians(float(previous.latitude)), radians(float(previous.longitude))
            lat2, lon2 = radians(float(self.latitude)), radians(float(self.longitude))
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            R = 6371  # Rayon de la Terre en km
            
            return R * c
        return 0
    
    def get_place_name(self):
        """Convertit les coordonnées GPS en nom de lieu."""
        # Utiliser le cache pour éviter des appels répétés à l'API
        cache_key = f'place_name_{self.latitude}_{self.longitude}'
        place_name = cache.get(cache_key)
        if not place_name:
            geolocator = Nominatim(user_agent="transport_management")
            location = geolocator.reverse((self.latitude, self.longitude), exactly_one=True)
            place_name = location.address if location else "Lieu inconnu"
            # Stocker le résultat dans le cache pendant 1 heure
            cache.set(cache_key, place_name, timeout=3600)
        return place_name

    def update_trip_location(self):
        """Met à jour la localisation dans Trip et DisplaySchedule"""
        if self.is_valid:
            # Mise à jour du Trip
            self.trip.current_location = f"{self.latitude},{self.longitude}"
            self.trip.save()

            # Mise à jour du DisplaySchedule associé
            displays = self.trip.displayschedule_set.all()
            for display in displays:
                display.current_location = f"{self.latitude},{self.longitude}"
                display.location_coordinates = {
                    'latitude': str(self.latitude),
                    'longitude': str(self.longitude),
                    'timestamp': self.timestamp.isoformat()
                }
                display.save()

    def save(self, *args, **kwargs):
        # Validation avant sauvegarde
        self.is_valid = self.validate_position()
        
        super().save(*args, **kwargs)
        
        # Mise à jour des informations liées
        if self.is_valid:
            self.update_trip_location()

    @classmethod
    def get_latest_position(cls, trip_id):
        """Récupère la dernière position valide pour un voyage"""
        return cls.objects.filter(
            trip_id=trip_id,
            is_valid=True
        ).order_by('-timestamp').first()

    @classmethod
    def cleanup_old_positions(cls, days=7):
        """Nettoie les anciennes positions"""
        threshold = timezone.now() - timezone.timedelta(days=days)
        cls.objects.filter(timestamp__lt=threshold).delete()
        
        
class BusTracking(models.Model):
    LOCATION_SOURCE_CHOICES = [
        ('GPS', 'GPS'),
        ('Station', 'Station de Bus'),
        ('WiFi', 'Position via WiFi'),
        ('Manual', 'Entrée Manuelle'),
        ('cellular', 'Réseau Cellulaire'),
        ('beacon', 'Beacon'),
    ]

    VEHICLE_STATUS_CHOICES = [
        ('in_service', 'En Service'),
        ('out_of_service', 'Hors Service'),
        ('maintenance', 'En Maintenance'),
        ('garage', 'Au Garage'),
        ('unknown', 'Inconnu')
    ]

    BATTERY_STATUS_CHOICES = [
        ('full', 'Pleine'),
        ('high', 'Haute'),
        ('medium', 'Moyenne'),
        ('low', 'Faible'),
        ('critical', 'Critique'),
        ('charging', 'En charge')
    ]

    # Identification
    tracking_id = models.AutoField(primary_key=True)
    vehicle = models.ForeignKey(
        Vehicle, 
        on_delete=models.CASCADE, 
        help_text="Bus suivi",
        related_name='tracking_records'
    )

    # Localisation
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        help_text="Latitude en temps réel"
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        help_text="Longitude en temps réel"
    )
    altitude = models.DecimalField(
        max_digits=7, 
        decimal_places=2,
        null=True, blank=True,
        help_text="Altitude en mètres"
    )

    # Mouvement et vitesse
    speed = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        help_text="Vitesse en km/h"
    )
    heading = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        null=True, blank=True,
        help_text="Direction en degrés"
    )
    is_moving = models.BooleanField(
        default=False,
        help_text="Statut de mouvement"
    )

    # Source et précision
    location_source = models.CharField(
        max_length=100, 
        choices=LOCATION_SOURCE_CHOICES,
        default='GPS',
        help_text="Source des données de position"
    )
    accuracy = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        null=True, blank=True,
        help_text="Précision en mètres"
    )
    signal_strength = models.IntegerField(
        null=True, blank=True,
        help_text="Force du signal en pourcentage"
    )

    # Statuts
    vehicle_status = models.CharField(
        max_length=50,
        choices=VEHICLE_STATUS_CHOICES,
        default='unknown'
    )
    battery_status = models.CharField(
        max_length=50,
        choices=BATTERY_STATUS_CHOICES,
        null=True, blank=True
    )
    battery_level = models.IntegerField(
        null=True, blank=True,
        help_text="Niveau de batterie en pourcentage"
    )

    # Informations temporelles
    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="Horodatage de la position"
    )
    last_communication = models.DateTimeField(
        auto_now=True,
        help_text="Dernière communication avec le véhicule"
    )

    # Données additionnelles
    address = models.CharField(
        max_length=255,
        blank=True, null=True,
        help_text="Adresse approximative"
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Données additionnelles de tracking"
    )
    diagnostic_data = models.JSONField(
        default=dict,
        help_text="Données de diagnostic du véhicule"
    )

    class Meta:
        verbose_name = "Bus Tracking"
        verbose_name_plural = "Bus Trackings"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['vehicle', '-timestamp']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['vehicle_status']),
        ]

    def __str__(self):
        return f"Bus {self.vehicle.vehicle_number} - {self.vehicle_status} at {self.timestamp}"

    def save(self, *args, **kwargs):
        # Mise à jour du statut de mouvement
        if self.speed > 1:  # Plus de 1 km/h
            self.is_moving = True
        else:
            self.is_moving = False

        # Géocodage inverse pour obtenir l'adresse (à implémenter)
        if not self.address:
            self.get_address_from_coordinates()

        super().save(*args, **kwargs)

    def get_address_from_coordinates(self):
        """Obtient l'adresse à partir des coordonnées"""
        # Implémentation du géocodage inverse
        pass

    def calculate_distance_from_previous(self):
        """Calcule la distance depuis la dernière position"""
        previous = BusTracking.objects.filter(
            vehicle=self.vehicle,
            timestamp__lt=self.timestamp
        ).order_by('-timestamp').first()

        if previous:
            from math import radians, sin, cos, sqrt, atan2
            
            lat1, lon1 = radians(float(previous.latitude)), radians(float(previous.longitude))
            lat2, lon2 = radians(float(self.latitude)), radians(float(self.longitude))
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            R = 6371  # Rayon de la Terre en km
            
            return R * c
        return 0

    @property
    def is_active(self):
        """Vérifie si le tracking est actif"""
        return (timezone.now() - self.timestamp).total_seconds() < 300  # 5 minutes

    @property
    def current_trip(self):
        """Retourne le voyage en cours si le bus est en service"""
        if self.vehicle_status == 'in_service':
            return self.vehicle.trip_set.filter(
                status='in_progress'
            ).first()
        return None

    @classmethod
    def get_active_vehicles(cls):
        """Retourne tous les véhicules actifs"""
        recent_time = timezone.now() - timezone.timedelta(minutes=5)
        return cls.objects.filter(
            timestamp__gte=recent_time,
            vehicle_status='in_service'
        ).select_related('vehicle')

    @classmethod
    def cleanup_old_records(cls, days=30):
        """Nettoie les anciens enregistrements"""
        threshold = timezone.now() - timezone.timedelta(days=days)
        cls.objects.filter(timestamp__lt=threshold).delete()
        
        
class DriverNavigation(models.Model):
    NAVIGATION_PROVIDER_CHOICES = [
        ('google_maps', 'Google Maps'),
        ('waze', 'Waze'),
        ('here_maps', 'HERE Maps'),
        ('mapbox', 'Mapbox'),
        ('tomtom', 'TomTom'),
        ('internal', 'Système Interne')
    ]

    NAVIGATION_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('active', 'Active'),
        ('paused', 'En pause'),
        ('rerouting', 'Recalcul'),
        ('completed', 'Terminée'),
        ('failed', 'Échec')
    ]

    ROUTE_TYPE_CHOICES = [
        ('fastest', 'Plus rapide'),
        ('shortest', 'Plus court'),
        ('eco', 'Économique'),
        ('avoid_highways', 'Éviter autoroutes'),
        ('avoid_tolls', 'Éviter péages')
    ]

    # Identification et relations principales
    navigation_id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(
        Trip, 
        on_delete=models.CASCADE,
        related_name='navigations',
        help_text="Trajet associé"
    )
    rule_set = models.ForeignKey(
        RuleSet, 
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Règles de navigation"
    )

    # Configuration de navigation
    navigation_provider = models.CharField(
        max_length=50,
        choices=NAVIGATION_PROVIDER_CHOICES,
        default='google_maps'
    )
    provider_settings = models.JSONField(
        default=dict,
        help_text="Paramètres spécifiques au fournisseur"
    )
    route_type = models.CharField(
        max_length=20,
        choices=ROUTE_TYPE_CHOICES,
        default='fastest'
    )

    # Statut et progression
    navigation_status = models.CharField(
        max_length=20,
        choices=NAVIGATION_STATUS_CHOICES,
        default='pending'
    )
    next_stop = models.ForeignKey(
        Stop, 
        on_delete=models.SET_NULL,
        null=True,
        related_name='navigations_to',
        help_text="Prochain arrêt"
    )

    # Instructions et itinéraire
    route_details = models.JSONField(
        default=dict,
        help_text="Détails complets de l'itinéraire"
    )
    current_step = models.JSONField(
        default=dict,
        help_text="Étape actuelle de navigation"
    )
    remaining_steps = models.JSONField(
        default=list,
        help_text="Étapes restantes"
    )

    # Estimations
    estimated_arrival = models.DateTimeField(
        help_text="Heure d'arrivée estimée"
    )
    estimated_duration = models.DurationField(
        null=True,
        help_text="Durée estimée restante"
    )
    estimated_distance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        help_text="Distance restante en km"
    )

    # Alertes et notifications
    alerts = models.JSONField(
        default=list,
        help_text="Alertes actives"
    )
    traffic_info = models.JSONField(
        default=dict,
        help_text="Informations trafic"
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync = models.DateTimeField(
        null=True,
        help_text="Dernière synchronisation avec le provider"
    )

    class Meta:
        verbose_name = "Driver Navigation"
        verbose_name_plural = "Driver Navigations"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['trip', '-updated_at']),
            models.Index(fields=['navigation_status']),
        ]

    def __str__(self):
        return f"Navigation for Trip {self.trip.id} - {self.navigation_status}"

    @property
    def driver(self):
        """Accède au chauffeur via le voyage"""
        return self.trip.driver if self.trip else None

    @property
    def vehicle(self):
        """Accède au véhicule via le voyage"""
        return self.trip.vehicle if self.trip else None

    @property
    def current_location(self):
        """Obtient la position actuelle via BusTracking"""
        return self.trip.vehicle.tracking_records.latest('timestamp') if self.trip and self.trip.vehicle else None

    def initialize_navigation(self):
        """Initialise la navigation avec le provider sélectionné"""
        if self.navigation_provider == 'google_maps':
            self.initialize_google_maps()
        elif self.navigation_provider == 'waze':
            self.initialize_waze()
        # Ajouter d'autres providers selon besoin

    def update_route(self):
        """Met à jour l'itinéraire en fonction de la position actuelle"""
        current_location = self.current_location
        if current_location:
            self.update_provider_route(
                current_location.latitude,
                current_location.longitude
            )

    def update_provider_route(self, lat, lon):
        """Met à jour l'itinéraire avec le provider"""
        if self.navigation_provider == 'google_maps':
            self.update_google_maps_route(lat, lon)
        # Ajouter d'autres providers

    def handle_rerouting(self):
        """Gère le recalcul d'itinéraire"""
        self.navigation_status = 'rerouting'
        self.update_route()
        self.save()

    def process_traffic_update(self, traffic_data):
        """Traite les mises à jour de trafic"""
        self.traffic_info = traffic_data
        self.recalculate_estimates()
        self.save()

    def recalculate_estimates(self):
        """Recalcule les estimations"""
        # Logique de recalcul
        pass

    def add_alert(self, alert_type, message):
        """Ajoute une alerte"""
        alert = {
            'type': alert_type,
            'message': message,
            'timestamp': timezone.now().isoformat()
        }
        if isinstance(self.alerts, list):
            self.alerts.append(alert)
        else:
            self.alerts = [alert]
        self.save()

    # Méthodes spécifiques aux providers
    def initialize_google_maps(self):
        """Initialise la navigation Google Maps"""
        # Implémentation de l'intégration Google Maps
        pass

    def initialize_waze(self):
        """Initialise la navigation Waze"""
        # Implémentation de l'intégration Waze
        pass

    @classmethod
    def get_active_navigations(cls):
        """Récupère toutes les navigations actives"""
        return cls.objects.filter(
            navigation_status__in=['active', 'rerouting']
        )
        
class PassengerTripHistory(models.Model):
    STATUS_CHOICES = [
        ('completed', 'Complété'),
        ('canceled', 'Annulé'),
        ('no_show', 'Non présenté'),
        ('interrupted', 'Interrompu'),
        ('refunded', 'Remboursé')
    ]

    SATISFACTION_CHOICES = [
        (1, 'Très insatisfait'),
        (2, 'Insatisfait'),
        (3, 'Neutre'),
        (4, 'Satisfait'),
        (5, 'Très satisfait')
    ]

    # Relations principales
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='trip_history'
    )
    trip = models.ForeignKey(
        Trip, 
        on_delete=models.CASCADE,
        related_name='passenger_history'
    )

    # Informations du voyage
    trip_date = models.DateTimeField(
        default=timezone.now,
        help_text="Date et heure du voyage"
    )
    boarding_time = models.DateTimeField(
        null=True, blank=True,
        help_text="Heure d'embarquement"
    )
    alighting_time = models.DateTimeField(
        null=True, blank=True,
        help_text="Heure de descente"
    )

    # Points de départ et d'arrivée
    origin_stop = models.ForeignKey(
        'Stop',
        on_delete=models.SET_NULL,
        null=True,
        related_name='history_as_origin'
    )
    destination_stop = models.ForeignKey(
        'Stop',
        on_delete=models.SET_NULL,
        null=True,
        related_name='history_as_destination'
    )

    # Statut et détails du voyage
    status = models.CharField(
        max_length=100,
        choices=STATUS_CHOICES,
        default='completed'
    )
    status_details = models.JSONField(
        default=dict,
        help_text="Détails du statut du voyage"
    )

    # Tarification et paiement
    fare_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True
    )
    refund_status = models.JSONField(
        default=dict,
        help_text="Informations sur le remboursement si applicable"
    )

    # Retour d'expérience
    satisfaction_rating = models.IntegerField(
        choices=SATISFACTION_CHOICES,
        null=True, blank=True
    )
    feedback = models.JSONField(
        default=dict,
        help_text="Retour d'expérience détaillé"
    )
    reported_issues = models.JSONField(
        default=list,
        help_text="Problèmes signalés pendant le voyage"
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    modification_history = models.JSONField(
        default=list,
        help_text="Historique des modifications"
    )

    class Meta:
        verbose_name = "Passenger Trip History"
        verbose_name_plural = "Passenger Trip Histories"
        ordering = ['-trip_date']
        indexes = [
            models.Index(fields=['user', '-trip_date']),
            models.Index(fields=['trip', 'status']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.trip} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Calculer la durée du voyage si possible
        if self.boarding_time and self.alighting_time:
            self.status_details['duration'] = (
                self.alighting_time - self.boarding_time
            ).total_seconds() / 60  # en minutes

        if not self.trip_date:
            self.trip_date = self.trip.trip_date

        super().save(*args, **kwargs)

    @property
    def trip_duration(self):
        """Calcule la durée du voyage en minutes"""
        if self.boarding_time and self.alighting_time:
            return (self.alighting_time - self.boarding_time).total_seconds() / 60
        return None

    @property
    def origin(self):
        """Retourne le nom de l'arrêt d'origine"""
        return self.origin_stop.name if self.origin_stop else None

    @property
    def destination(self):
        """Retourne le nom de l'arrêt de destination"""
        return self.destination_stop.name if self.destination_stop else None

    def add_feedback(self, rating, comment=None, issues=None):
        """Ajoute un retour d'expérience"""
        self.satisfaction_rating = rating
        feedback_entry = {
            'rating': rating,
            'comment': comment,
            'timestamp': timezone.now().isoformat()
        }
        if isinstance(self.feedback, dict):
            self.feedback = feedback_entry
        
        if issues:
            if isinstance(self.reported_issues, list):
                self.reported_issues.extend(issues)
            else:
                self.reported_issues = issues
                
        self.save()

    def process_refund(self, amount, reason):
        """Traite un remboursement"""
        refund_info = {
            'amount': amount,
            'reason': reason,
            'processed_at': timezone.now().isoformat(),
            'original_fare': self.fare_paid
        }
        self.refund_status = refund_info
        self.status = 'refunded'
        self.save()

    def log_modification(self, action_type, details):
        """Enregistre une modification"""
        modification = {
            'action': action_type,
            'details': details,
            'timestamp': timezone.now().isoformat()
        }
        if isinstance(self.modification_history, list):
            self.modification_history.append(modification)
        else:
            self.modification_history = [modification]
        self.save()

    @classmethod
    def get_user_history(cls, user_id, start_date=None, end_date=None):
        """Récupère l'historique des voyages d'un utilisateur"""
        queryset = cls.objects.filter(user_id=user_id)
        if start_date:
            queryset = queryset.filter(trip_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(trip_date__lte=end_date)
        return queryset.order_by('-trip_date')

    @classmethod
    def get_trip_statistics(cls, user_id):
        """Calcule les statistiques des voyages d'un utilisateur"""
        trips = cls.objects.filter(user_id=user_id)
        return {
            'total_trips': trips.count(),
            'completed_trips': trips.filter(status='completed').count(),
            'canceled_trips': trips.filter(status='canceled').count(),
            'total_spent': sum(trip.fare_paid for trip in trips),
            'average_rating': trips.filter(satisfaction_rating__isnull=False)
                                .aggregate(models.Avg('satisfaction_rating'))
                                ['satisfaction_rating__avg']
        }
        
class TransactionScan(models.Model):
    SCAN_TYPE_CHOICES = [
        ('nfc_physical', 'Carte NFC Physique'),
        ('nfc_virtual', 'NFC Virtuel (Téléphone)'),
        ('qr_code', 'Code QR'),
        ('barcode', 'Code-barres'),
        ('manual', 'Entrée Manuelle'),
        ('biometric', 'Biométrique')
    ]

    SCAN_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('successful', 'Réussi'),
        ('failed', 'Échoué'),
        ('expired', 'Expiré'),
        ('invalid', 'Invalid'),
        ('duplicate', 'Doublon')
    ]

    VERIFICATION_STATUS_CHOICES = [
        ('not_verified', 'Non vérifié'),
        ('verified', 'Vérifié'),
        ('verification_failed', 'Échec de vérification'),
        ('requires_manual', 'Vérification manuelle requise')
    ]

    # Relations principales
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='scans'
    )
    card = models.ForeignKey(
        CardInfo, 
        on_delete=models.CASCADE,
        related_name='scans'
    )
    trip = models.ForeignKey(
        Trip, 
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='passenger_scans'
    )

    # Informations de scan
    scan_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Identifiant unique du scan"
    )
    scan_type = models.CharField(
        max_length=50,
        choices=SCAN_TYPE_CHOICES
    )
    scan_data = models.JSONField(
        default=dict,
        help_text="Données brutes du scan"
    )

    # Statut et vérification
    scan_status = models.CharField(
        max_length=20,
        choices=SCAN_STATUS_CHOICES,
        default='pending'
    )
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='not_verified'
    )

    # Temporalité
    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="Moment du scan"
    )
    verification_timestamp = models.DateTimeField(
        null=True, blank=True,
        help_text="Moment de la vérification"
    )
    expiry_time = models.DateTimeField(
        null=True, blank=True,
        help_text="Délai d'expiration du scan"
    )

    # Validation et erreurs
    is_valid = models.BooleanField(
        default=False,
        help_text="Indique si le scan est valide"
    )
    failure_reason = models.CharField(
        max_length=255,
        null=True, blank=True
    )
    error_details = models.JSONField(
        default=dict,
        help_text="Détails des erreurs"
    )

    # Localisation
    station_id = models.CharField(
        max_length=50,
        null=True, blank=True,
        help_text="ID de la station de scan"
    )
    location_data = models.JSONField(
        default=dict,
        help_text="Données de localisation du scan"
    )

    # Métadonnées
    device_info = models.JSONField(
        default=dict,
        help_text="Informations sur l'appareil de scan"
    )
    operator_id = models.CharField(
        max_length=50,
        null=True, blank=True,
        help_text="ID de l'opérateur si scan manuel"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Transaction Scan"
        verbose_name_plural = "Transaction Scans"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['card', '-timestamp']),
            models.Index(fields=['scan_status']),
        ]

    def __str__(self):
        return f"Scan {self.scan_id} - {self.user.username} ({self.get_scan_status_display()})"

    def save(self, *args, **kwargs):
        # Génération de l'ID unique si nouveau scan
        if not self.scan_id:
            self.scan_id = self.generate_scan_id()
        
        # Définition du délai d'expiration si non défini
        if not self.expiry_time:
            self.expiry_time = timezone.now() + timezone.timedelta(minutes=30)

        super().save(*args, **kwargs)

    def generate_scan_id(self):
        """Génère un ID unique pour le scan"""
        import uuid
        return f"SCAN-{timezone.now().strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}"

    def verify_scan(self):
        """Vérifie la validité du scan"""
        # Vérification de l'expiration
        if timezone.now() > self.expiry_time:
            self.scan_status = 'expired'
            self.is_valid = False
            self.save()
            return False

        # Vérification des doublons
        recent_scan = TransactionScan.objects.filter(
            user=self.user,
            trip=self.trip,
            scan_status='successful',
            timestamp__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).exclude(id=self.id).first()

        if recent_scan:
            self.scan_status = 'duplicate'
            self.is_valid = False
            self.save()
            return False

        # Autres vérifications...
        return True

    def process_scan(self):
        """Traite le scan"""
        if self.verify_scan():
            # Vérification de la carte
            if self.verify_card():
                self.scan_status = 'successful'
                self.is_valid = True
                self.verification_status = 'verified'
                self.verification_timestamp = timezone.now()
            else:
                self.scan_status = 'failed'
                self.failure_reason = 'Invalid card'
        self.save()

    def verify_card(self):
        """Vérifie la validité de la carte"""
        # Logique de vérification de la carte
        return True

    @property
    def is_expired(self):
        """Vérifie si le scan est expiré"""
        return timezone.now() > self.expiry_time

    @classmethod
    def get_recent_scans(cls, user_id):
        """Récupère les scans récents d'un utilisateur"""
        return cls.objects.filter(
            user_id=user_id,
            timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
        )

    @classmethod
    def get_trip_scans(cls, trip_id):
        """Récupère tous les scans pour un voyage"""
        return cls.objects.filter(trip_id=trip_id)

    @classmethod
    def cleanup_old_scans(cls, days=30):
        """Nettoie les anciens scans"""
        threshold = timezone.now() - timezone.timedelta(days=days)
        cls.objects.filter(timestamp__lt=threshold).delete()