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

    # Nouveaux champs pour la gestion des statuts
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
        """
        Archive l'horaire.
        """
        self.status = 'archived'
        self.is_active = False
        self.is_current_version = False
        self.save()

    def create_new_version(self):
        """
        Crée une nouvelle version de l'horaire.
        """
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

    def clean(self):
        """
        Validation des données avant sauvegarde.
        """
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
        """
        Trouve le prochain départ à partir d'une heure donnée.
        """
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
        """
        Retourne l'historique des validations formaté.
        """
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











































































