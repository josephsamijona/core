from django.db import models
from django.conf import settings
from geopy.distance import geodesic
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from inventory_management.models import Vehicle
from membership_management.models import CardInfo
from datetime import timedelta, time, datetime, date

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
    route = models.ForeignKey('Route', on_delete=models.CASCADE, related_name='schedules')

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

    # Statut et validation
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    approval_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_schedules'
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
        ordering = ['route', 'day_of_week', 'start_time']
        unique_together = [
            ('route', 'day_of_week', 'start_time', 'schedule_version'),
            ('schedule_code', 'schedule_version')
        ]

    def generate_timepoints_for_date(self, date):
        """
        Génère les horaires pour une date spécifique en tenant compte des ajustements.
        """
        times = []
        current_datetime = datetime.combine(date, self.start_time)
        end_datetime = datetime.combine(date, self.end_time)

        # Déterminer la fréquence applicable
        frequency = self.frequency
        if self.peak_hours_frequency and self.is_peak_hour(current_datetime.time()):
            frequency = self.peak_hours_frequency
        elif self.off_peak_frequency:
            frequency = self.off_peak_frequency

        while current_datetime <= end_datetime:
            times.append(current_datetime.strftime('%H:%M:%S'))
            current_datetime += timedelta(minutes=frequency)
            # Ajuster la fréquence si nécessaire
            if self.peak_hours_frequency and self.is_peak_hour(current_datetime.time()):
                frequency = self.peak_hours_frequency
            else:
                frequency = self.frequency

        self.timepoints = times
        self.save()

    def is_peak_hour(self, time):
        """
        Détermine si l'heure donnée est une heure de pointe.
        """
        # Exemple simple : heures de pointe entre 7h-9h et 17h-19h
        peak_hours = [
            (datetime.strptime('07:00', '%H:%M').time(), datetime.strptime('09:00', '%H:%M').time()),
            (datetime.strptime('17:00', '%H:%M').time(), datetime.strptime('19:00', '%H:%M').time()),
        ]
        for start, end in peak_hours:
            if start <= time <= end:
                return True
        return False

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("L'heure de fin doit être après l'heure de début")
        if self.frequency <= 0:
            raise ValidationError("La fréquence doit être positive")

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














































































