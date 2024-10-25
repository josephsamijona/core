from django.db import models
from django.conf import settings
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
    



















































































# Constantes spécifiques à Haïti
HAITI_HOLIDAYS_CHOICES = [
    ('1er janvier', 'Jour de l\'Indépendance'),
    ('2 janvier', 'Jour des Aïeux'),
    ('Mardi Gras', 'Mardi Gras (Varie chaque année)'),
    ('Mercredi des Cendres', 'Mercredi des Cendres (Varie chaque année)'),
    ('Vendredi Saint', 'Vendredi Saint (Varie chaque année)'),
    ('1er mai', 'Fête du Travail et de l\'Agriculture'),
    ('18 mai', 'Jour du Drapeau et de l\'Université'),
    ('15 août', 'Assomption'),
    ('17 octobre', 'Anniversaire de la mort de Jean-Jacques Dessalines'),
    ('1er novembre', 'Toussaint'),
    ('2 novembre', 'Jour des Morts'),
    ('18 novembre', 'Bataille de Vertières'),
    ('25 décembre', 'Noël'),
]

EMERGENCY_REASONS_CHOICES = [
    ('manifestation', 'Manifestation'),
    ('barricade', 'Barricade'),
    ('cyclone', 'Cyclone'),
    ('inondation', 'Inondation'),
    ('pluie_intense', 'Pluie intense'),
    ('insecurity', 'Insécurité'),
    ('guerre', 'Guerre'),
]

ACTIVE_DAYS_CHOICES = [
    ('Lundi', 'Lundi'),
    ('Mardi', 'Mardi'),
    ('Mercredi', 'Mercredi'),
    ('Jeudi', 'Jeudi'),
    ('Vendredi', 'Vendredi'),
    ('Samedi', 'Samedi'),
    ('Dimanche', 'Dimanche'),
]

DAY_SCHEDULES_PRESETS = {
    'Jour de Semaine Standard': {
        'Lundi': ['08:00-10:00', '14:00-16:00'],
        'Mardi': ['08:00-10:00', '14:00-16:00'],
        'Mercredi': ['08:00-10:00', '14:00-16:00'],
        'Jeudi': ['08:00-10:00', '14:00-16:00'],
        'Vendredi': ['08:00-12:00']
    },
    'Weekend': {
        'Samedi': ['10:00-12:00'],
        'Dimanche': []
    },
    'Evénement Spécial': {
        'Samedi': ['08:00-18:00']
    }
}

RESOURCE_THRESHOLDS_PRESETS = {
    'Minimum': {
        'minimum_buses': 3,
        'minimum_drivers': 5
    },
    'Moyen': {
        'minimum_buses': 5,
        'minimum_drivers': 7
    },
    'Maximum': {
        'minimum_buses': 10,
        'minimum_drivers': 12
    }
}

class OperationalControlPlan(models.Model):
    # Champs existants
    name = models.CharField(max_length=255)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=False)
    is_renewed = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Champs existants pour la gestion automatisée
    min_drivers_per_shift = models.IntegerField(default=1)
    min_vehicles_per_shift = models.IntegerField(default=1)
    buffer_time_between_trips = models.IntegerField(default=15)  # en minutes
    max_consecutive_hours_per_driver = models.IntegerField(default=8)
    passenger_load_factor = models.FloatField(default=0.8)  # 80% de la capacité du véhicule
    maintenance_interval_km = models.IntegerField(default=5000)
    frequency = models.IntegerField(default=30)
    emergency_reserve_vehicles = models.IntegerField(default=1)
    
    # Nouveaux champs
    circuit_configuration = models.JSONField(default=dict, help_text="Configuration des circuits (A, B, C, etc.) avec leurs caractéristiques spécifiques")
    performance_targets = models.JSONField(default=dict, help_text="Objectifs de performance pour les trajets (ex: ponctualité, satisfaction client)")
    pricing_rules = models.JSONField(default=dict, help_text="Règles de tarification pour les différents types de trajets et de passagers")
    notification_settings = models.JSONField(default=dict, help_text="Configuration des notifications pour les différents événements (retards, incidents, etc.)")
    transfer_rules = models.JSONField(default=dict, help_text="Règles pour la gestion des correspondances entre les différents circuits")
    
    # Champs pour la gestion des horaires et des jours spéciaux
    active_days = models.JSONField(default=dict, help_text="Jours où les trajets sont actifs")
    inactive_days = models.JSONField(default=dict, help_text="Jours où les trajets ne sont pas actifs")
    holidays = models.JSONField(default=dict, help_text="Jours fériés où les trajets ne sont pas planifiés")
    day_schedules = models.JSONField(default=dict, help_text="Horaires des trajets par jour")
    
    # Champs pour la sélection des jours actifs/inactifs et des jours fériés
    preselected_active_days = models.CharField(max_length=50, choices=ACTIVE_DAYS_CHOICES, blank=True, null=True)
    preselected_inactive_days = models.CharField(max_length=50, choices=ACTIVE_DAYS_CHOICES, blank=True, null=True)
    preselected_holidays = models.CharField(max_length=50, choices=HAITI_HOLIDAYS_CHOICES, blank=True, null=True)
    
    # Champ pour la sélection des horaires prédéfinis
    preselected_day_schedules = models.CharField(
        max_length=50,
        choices=[(key, key) for key in DAY_SCHEDULES_PRESETS.keys()],
        blank=True,
        null=True
    )
    
    # Champs pour la gestion des situations exceptionnelles
    special_changes = models.JSONField(default=dict, help_text="Changements temporaires affectant les trajets (ajouts, suppressions)")
    fallback_conditions = models.JSONField(default=dict, help_text="Conditions de fallback en cas de problème")
    override_conditions = models.JSONField(default=dict, help_text="Instructions spéciales pour remplacer des trajets existants en cas d'urgence")
    emergency_protocols = models.JSONField(default=dict, help_text="Protocoles à suivre en cas d'urgence ou de perturbation majeure")
    
    # Champ pour la sélection des raisons d'urgence
    preselected_emergency_reasons = models.CharField(max_length=50, choices=EMERGENCY_REASONS_CHOICES, blank=True, null=True)
    
    # Champ pour la sélection des seuils de ressources
    preselected_resource_thresholds = models.CharField(
        max_length=50,
        choices=[(key, key) for key in RESOURCE_THRESHOLDS_PRESETS.keys()],
        blank=True,
        null=True
    )
    
    def save(self, *args, **kwargs):
        if isinstance(self.start_date, str):
            self.start_date = timezone.make_aware(datetime.strptime(self.start_date, "%Y-%m-%d"))
        elif isinstance(self.start_date, datetime) and timezone.is_naive(self.start_date):
            self.start_date = timezone.make_aware(self.start_date)
        
        if isinstance(self.end_date, str):
            self.end_date = timezone.make_aware(datetime.strptime(self.end_date, "%Y-%m-%d"))
        elif isinstance(self.end_date, datetime) and timezone.is_naive(self.end_date):
            self.end_date = timezone.make_aware(self.end_date)
        
        super().save(*args, **kwargs)
        
    def generate_schedules(self):
        Schedule.objects.filter(ocp=self).delete()  # Supprime les anciens horaires

        for day in self.active_days:
            for route in Route.objects.filter(ocp=self):
                # Obtenir les heures de début et de fin en tant qu'objets datetime.time
                start_time = datetime.strptime(self.day_schedules[day]['start'], "%H:%M").time()
                end_time = datetime.strptime(self.day_schedules[day]['end'], "%H:%M").time()
                
                # Combiner avec une date pour obtenir des objets datetime.datetime
                current_time = datetime.combine(timezone.now().date(), start_time)
                end_datetime = datetime.combine(timezone.now().date(), end_time)

                while current_time < end_datetime:
                    end_trip_time = current_time + timedelta(minutes=self.buffer_time_between_trips)
                    Schedule.objects.create(
                        ocp=self,
                        route=route,
                        start_time=current_time,
                        end_time=end_trip_time,
                        frequency=self.frequency,
                        day_of_week=day
                    )
                    current_time += timedelta(minutes=self.frequency)

                    
                    
    def create_exception_schedule(self, date, routes, start_time, end_time, frequency):
        day_of_week = date.strftime("%A").lower()
        
        # Désactiver les horaires réguliers pour cette date
        Schedule.objects.filter(ocp=self, day_of_week=day_of_week, is_active=True).update(is_active=False)

        # Combiner les temps avec la date fournie
        current_time = datetime.combine(date, start_time)
        end_datetime = datetime.combine(date, end_time)

        # Créer de nouveaux horaires exceptionnels
        for route in routes:
            while current_time < end_datetime:
                end_trip_time = current_time + timedelta(minutes=self.buffer_time_between_trips)
                Schedule.objects.create(
                    ocp=self,
                    route=route,
                    start_time=current_time,
                    end_time=end_trip_time,
                    frequency=frequency,
                    day_of_week=day_of_week,
                    is_exception=True,
                    exception_date=date
                )
                current_time += timedelta(minutes=frequency)

                
    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"

class Destination(models.Model):
    # Champs principaux
    name = models.CharField(max_length=255, default='', help_text="Nom de la destination")
    localite = models.CharField(max_length=255, default='Unknown', help_text="Localité de la destination")
    circuit = models.CharField(max_length=50, default='A', help_text="Circuit associé à cette destination")

    # Champs additionnels inspirés des modèles Route et Stop
    gps_coordinates = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Coordonnées GPS de la destination (latitude, longitude)"
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Adresse physique de la destination"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description détaillée de la destination"
    )
    type = models.CharField(
        max_length=50,
        help_text="Type de la destination (ex: urbain, touristique)",
        default='touristique'
    )
    accessibility = models.BooleanField(
        default=False,
        help_text="Indique si la destination est accessible aux personnes à mobilité réduite"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indique si la destination est active"
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="Date de création de la destination"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date de la dernière mise à jour de la destination"
    )

    # Méthodes spéciales
    def __str__(self):
        return f"{self.name} - {self.localite}"

    def save(self, *args, **kwargs):
        # Mise à jour automatique des coordonnées GPS si non fournies
        if not self.gps_coordinates and hasattr(self, 'latitude') and hasattr(self, 'longitude'):
            self.gps_coordinates = f"{self.latitude},{self.longitude}"
        super().save(*args, **kwargs)
        
        
class Stop(models.Model):
    # Champs existants
    name = models.CharField(max_length=255)
    latitude = models.FloatField(default='')
    longitude = models.FloatField(default='')
    service_zone = models.CharField(max_length=100, default='Unknown')
    circuit = models.CharField(max_length=50, default='a')
    ocp = models.ForeignKey(OperationalControlPlan, on_delete=models.CASCADE)

    # Nouveaux champs
    gps_coordinates = models.CharField(max_length=255, help_text="Coordonnées GPS de l'arrêt (latitude, longitude)", blank=True, null=True)
    address = models.CharField(max_length=255, help_text="Adresse de l'arrêt", blank=True, null=True)
    stop_type = models.CharField(
        max_length=50, 
        choices=[('bus_stop', 'Arrêt de bus'), ('station', 'Station'), ('terminal', 'Terminal')],
        help_text="Type de l'arrêt",
        default='bus_stop'
    )
    facilities = models.TextField(blank=True, null=True, help_text="Facilités à cet arrêt (ex: toilettes, abri)")
    accessibility = models.BooleanField(default=False, help_text="Indique si l'arrêt est accessible aux personnes à mobilité réduite")
    is_active = models.BooleanField(default=True, help_text="Statut de l'arrêt (actif/inactif)")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Stop: {self.name} - {self.service_zone}"

    def save(self, *args, **kwargs):
        # Mise à jour automatique des coordonnées GPS si non fournies
        if not self.gps_coordinates:
            self.gps_coordinates = f"{self.latitude},{self.longitude}"
        super().save(*args, **kwargs)

class Route(models.Model):
    # Champs existants
    name = models.CharField(max_length=255, help_text="Nom ou numéro de la route")
    circuit = models.CharField(max_length=50, default='A', help_text="Circuit de la route (ex: A, B, C)")
    stops = models.ManyToManyField(Stop, through='RouteStop')
    ocp = models.ForeignKey(OperationalControlPlan, on_delete=models.CASCADE)

    # Nouveaux champs
    type = models.CharField(max_length=50, help_text="Type de la route (ex: urbain, interurbain)", default='a')
    direction = models.CharField(max_length=50, help_text="Direction de la route (ex: nord-sud)",default='a')
    service_hours = models.CharField(max_length=100, help_text="Heures de service de la route (ex: 06:00 - 22:00)", default='a')
    frequency = models.CharField(max_length=100, help_text="Fréquence des trajets (ex: toutes les 30 minutes)",default='a')
    operating_days = models.JSONField(default=list, help_text="Jours d'exploitation de la route (ex: ['Lundi', 'Mardi'])")
    path = models.TextField(help_text="Description textuelle ou données géographiques du trajet",default='a')
    distance = models.DecimalField(max_digits=6, decimal_places=2, help_text="Distance totale de la route en kilomètres", default=0)
    status = models.CharField(max_length=50, choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', help_text="Statut de la route")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.direction})"

    class Meta:
        verbose_name = "Route"
        verbose_name_plural = "Routes"

    def get_total_stops(self):
        return self.stops.count()

    def activate(self):
        self.status = 'active'
        self.save()

    def deactivate(self):
        self.status = 'inactive'
        self.save()

    def add_stop(self, stop, order):
        RouteStop.objects.create(route=self, stop=stop, order=order)

    def remove_stop(self, stop):
        RouteStop.objects.filter(route=self, stop=stop).delete()

    def get_stops_in_order(self):
        return self.stops.order_by('routestop__order')

class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE)
    order = models.IntegerField()

    class Meta:
        ordering = ['order']
        unique_together = ('route', 'stop')

    def __str__(self):
        return f"{self.route.name} - Stop {self.stop.name} (Order: {self.order})"
    

class Driver(models.Model):
    # Champs existants
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    license_number = models.CharField(max_length=50, unique=True, default='')
    experience_years = models.IntegerField(default=0)
    ocp = models.ForeignKey(OperationalControlPlan, on_delete=models.CASCADE)

    # Nouveaux champs avec valeurs par défaut
    first_name = models.CharField(max_length=100, default='', blank=True, help_text="Prénom du chauffeur")
    last_name = models.CharField(max_length=100, default='', blank=True, help_text="Nom de famille du chauffeur")
    date_of_birth = models.DateField(null=True, blank=True, help_text="Date de naissance du chauffeur")
    license_expiry_date = models.DateField(null=True, blank=True, help_text="Date d'expiration du permis de conduire")
    contact_number = models.CharField(max_length=20, default='', blank=True, help_text="Numéro de téléphone du chauffeur")
    address = models.CharField(max_length=255, default='', blank=True, help_text="Adresse résidentielle du chauffeur")
    
    employment_status = models.CharField(
        max_length=50, 
        choices=[('active', 'Actif'), ('on_leave', 'En congé'), ('suspended', 'Suspendu'), ('terminated', 'Licencié')],
        default='active', 
        help_text="Statut d'emploi actuel"
    )
    availability_status = models.CharField(
        max_length=50, 
        choices=[('available', 'Disponible'), ('unavailable', 'Indisponible')],
        default='available', 
        help_text="Statut de disponibilité pour conduire"
    )
    
    last_trip_date = models.DateField(null=True, blank=True, help_text="Date du dernier trajet effectué")
    incident_history = models.JSONField(default=list, blank=True, help_text="Historique des incidents ou accidents de conduite")
    certifications = models.JSONField(default=list, blank=True, help_text="Certifications supplémentaires (ex: transport de passagers, conduite de véhicules lourds)")
    
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, blank=True, help_text="Évaluation du chauffeur (score sur 5)")
    total_trips = models.IntegerField(default=0, help_text="Nombre total de trajets effectués")
    driver_notes = models.TextField(default='', blank=True, help_text="Notes additionnelles ou commentaires sur le chauffeur")
    
    created_at = models.DateTimeField(default=timezone.now, help_text="Date d'ajout du chauffeur dans le système")
    updated_at = models.DateTimeField(default=timezone.now, help_text="Date de la dernière mise à jour des informations du chauffeur")

    def __str__(self):
        return f"Driver {self.user.get_full_name()} (License: {self.license_number})"

    def is_license_valid(self):
        return self.license_expiry_date > timezone.now().date() if self.license_expiry_date else False

    def update_rating(self, new_rating):
        if self.rating:
            self.rating = (self.rating + new_rating) / 2
        else:
            self.rating = new_rating
        self.save()

    def increment_total_trips(self):
        self.total_trips += 1
        self.save()

    def add_incident(self, incident_description):
        self.incident_history.append({
            'date': str(timezone.now().date()),
            'description': incident_description
        })
        self.save()

    def add_certification(self, certification):
        self.certifications.append(certification)
        self.save()

    class Meta:
        verbose_name = "Driver"
        verbose_name_plural = "Drivers"

class Schedule(models.Model):
    DAY_CHOICES = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]

    ocp = models.ForeignKey(OperationalControlPlan, on_delete=models.CASCADE, related_name='schedules')
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    start_time = models.DateTimeField()  # Changez ceci en DateTimeField
    end_time = models.DateTimeField()    # Changez ceci en DateTimeField
    frequency = models.PositiveIntegerField(help_text="Frequency in minutes")
    is_active = models.BooleanField(default=True)
    is_exception = models.BooleanField(default=False)
    exception_date = models.DateField(null=True, blank=True)
    day_of_week = models.CharField(max_length=10, choices=DAY_CHOICES, default='')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['ocp', 'route', 'start_time', 'day_of_week']

    def __str__(self):
        return f"{self.route.name}: {self.start_time} - {self.end_time} (every {self.frequency} min) on {self.day_of_week}"

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time.")
        if self.frequency <= 0:
            raise ValidationError("Frequency must be a positive integer.")

    def save(self, *args, **kwargs):
        if isinstance(self.start_time, str):
            self.start_time = timezone.datetime.fromisoformat(self.start_time)
        elif self.start_time is None:
            raise ValidationError("Start time cannot be None")

        if isinstance(self.end_time, str):
            self.end_time = timezone.datetime.fromisoformat(self.end_time)
        elif self.end_time is None:
            raise ValidationError("End time cannot be None")

        self.full_clean()  # Perform validation checks
        super().save(*args, **kwargs)


        
        

class DriverSchedule(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Planifié'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé')
    ]

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, help_text="Chauffeur concerné par ce planning")
    ocp = models.ForeignKey(OperationalControlPlan, on_delete=models.SET_NULL, null=True, blank=True, help_text="Lien vers le plan OCP")
    
    shift_start = models.DateTimeField(default=timezone.now,help_text="Début du shift du chauffeur")
    shift_end = models.DateTimeField(default=timezone.now, help_text="Fin du shift du chauffeur")
    
    breaks_scheduled = models.JSONField(default=dict, blank=True, help_text="Liste des pauses programmées (ex: {'pause1': '10:30-11:00', 'pause2': '15:00-15:30'})")
    
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='scheduled', help_text="Statut actuel du shift")
    is_active = models.BooleanField(default=False, help_text="Le shift est-il actif en ce moment ?")

    created_at = models.DateTimeField(default=timezone.now, help_text="Date de création du planning")
    updated_at = models.DateTimeField(default=timezone.now, help_text="Date de la dernière mise à jour du planning")

    # Nouveaux champs
    actual_start_time = models.DateTimeField(default=timezone.now,blank=True, help_text="Heure réelle de début du shift")
    actual_end_time = models.DateTimeField(default=timezone.now, blank=True, help_text="Heure réelle de fin du shift")
    notes = models.TextField(default="", blank=True, help_text="Notes additionnelles sur ce shift")

    def __str__(self):
        return f"Driver {self.driver} - {self.shift_start} to {self.shift_end}"
    
    class Meta:
        verbose_name = "Driver Schedule"
        verbose_name_plural = "Driver Schedules"
        unique_together = ('driver', 'shift_start', 'shift_end')

    def start_shift(self):
        self.status = 'in_progress'
        self.is_active = True
        self.actual_start_time = timezone.now()
        self.save()

    def end_shift(self):
        self.status = 'completed'
        self.is_active = False
        self.actual_end_time = timezone.now()
        self.save()

    def cancel_shift(self):
        self.status = 'cancelled'
        self.is_active = False
        self.save()

    def add_break(self, start_time, end_time):
        break_count = len(self.breaks_scheduled) + 1
        self.breaks_scheduled[f'pause{break_count}'] = f'{start_time}-{end_time}'
        self.save()

    def is_shift_overdue(self):
        return timezone.now() > self.shift_end and self.status != 'completed'

    def get_shift_duration(self):
        if self.actual_end_time and self.actual_start_time:
            return self.actual_end_time - self.actual_start_time
        elif self.actual_start_time:
            return timezone.now() - self.actual_start_time
        else:
            return None

class DriverVehicleAssignment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('active', 'Actif'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé')
    ]

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, help_text="Chauffeur assigné")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, help_text="Véhicule assigné")
    ocp = models.ForeignKey(OperationalControlPlan, on_delete=models.SET_NULL, null=True, blank=True, help_text="Plan OCP associé")

    assigned_from = models.DateTimeField(default=timezone.now,help_text="Date et heure de début de l'affectation")
    assigned_until = models.DateTimeField(default=timezone.now,help_text="Date et heure de fin de l'affectation")

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending', help_text="Statut de l'affectation")

    # Nouveaux champs
    actual_start = models.DateTimeField(default=timezone.now,null=True, blank=True, help_text="Date et heure réelle de début de l'affectation")
    actual_end = models.DateTimeField(default=timezone.now,null=True, blank=True, help_text="Date et heure réelle de fin de l'affectation")
    notes = models.TextField(blank=True, default="", help_text="Notes additionnelles sur cette affectation")
    created_at = models.DateTimeField(default=timezone.now, help_text="Date de création de l'affectation")
    updated_at = models.DateTimeField(default=timezone.now, help_text="Date de dernière mise à jour de l'affectation")

    def __str__(self):
        return f"{self.driver} assigned to {self.vehicle} from {self.assigned_from} to {self.assigned_until}"

    class Meta:
        verbose_name = "Driver-Vehicle Assignment"
        verbose_name_plural = "Driver-Vehicle Assignments"
        unique_together = ('driver', 'vehicle', 'assigned_from')

    def start_assignment(self):
        self.status = 'active'
        self.actual_start = timezone.now()
        self.save()

    def end_assignment(self):
        self.status = 'completed'
        self.actual_end = timezone.now()
        self.save()

    def cancel_assignment(self):
        self.status = 'cancelled'
        self.save()

    def is_active(self):
        now = timezone.now()
        return self.status == 'active' and self.assigned_from <= now <= self.assigned_until

    def is_overdue(self):
        return timezone.now() > self.assigned_until and self.status not in ['completed', 'cancelled']

    def get_duration(self):
        if self.actual_end and self.actual_start:
            return self.actual_end - self.actual_start
        elif self.actual_start:
            return timezone.now() - self.actual_start
        return None

    def extend_assignment(self, new_end_time):
        if new_end_time > self.assigned_until:
            self.assigned_until = new_end_time
            self.save()
        else:
            raise ValueError("New end time must be later than the current end time.")

    @classmethod
    def get_current_assignment(cls, driver):
        now = timezone.now()
        return cls.objects.filter(
            driver=driver,
            assigned_from__lte=now,
            assigned_until__gte=now,
            status='active'
        ).first()

class Trip(models.Model):
    # Champs existants
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='trips_as_driver')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    actual_end_time = models.DateTimeField(null=True, blank=True)
    ocp = models.ForeignKey(OperationalControlPlan, on_delete=models.CASCADE)
    actual_start_time = models.DateTimeField(null=True, blank=True)
    # Nouveaux champs
    passenger_count = models.PositiveIntegerField(default=0, help_text="Nombre de passagers pour ce voyage")
    origin = models.CharField(max_length=255, help_text="Lieu de départ",default='A')
    
    trip_date = models.DateTimeField(default=timezone.now, help_text="Date et heure du voyage")
    status = models.CharField(
        max_length=20,
        choices=[
            ('planned', 'Planifié'),
            ('in_progress', 'En cours'),
            ('completed', 'Terminé'),
            ('cancelled', 'Annulé')
        ],
        default='planned'
    )
    real_time_incidents = models.TextField(blank=True, null=True, help_text="Incidents survenus durant le voyage")
    departure_time = models.DateTimeField(null=True, blank=True, help_text="Heure de départ réelle")
    arrival_time = models.DateTimeField(null=True, blank=True, help_text="Heure d'arrivée réelle")

    def __str__(self):
        return f"Trip on {self.trip_date} by {self.driver.username} - {self.route.name if self.route else 'No Route'}"

    class Meta:
        verbose_name = "Trip"
        verbose_name_plural = "Trips"

    def increment_passenger_count(self):
        self.passenger_count += 1
        self.save()

    def start_trip(self):
        self.status = 'in_progress'
        self.departure_time = timezone.now()
        self.save()

    def end_trip(self):
        self.status = 'completed'
        self.arrival_time = timezone.now()
        self.save()

    def cancel_trip(self):
        self.status = 'cancelled'
        self.save()

    def add_incident(self, incident_description):
        if self.real_time_incidents:
            self.real_time_incidents += f"\n{timezone.now()}: {incident_description}"
        else:
            self.real_time_incidents = f"{timezone.now()}: {incident_description}"
        self.save()



class PassengerTrip(models.Model):
    BOARDING_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('boarded', 'À Bord'),
        ('boarding_failed', 'Échec Embarquement'),
        ('off_board', 'Descendu'),
        ('no_show', 'Non présenté')
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, help_text="Lien vers le trajet concerné")
    passenger = models.ForeignKey(User, on_delete=models.CASCADE, help_text="Le passager lié à ce voyage")
    boarding_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name='boarding_trips', default='')
    alighting_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name='alighting_trips', null=True, blank=True)
    boarding_time = models.DateTimeField(null=True, blank=True, help_text="Heure d'embarquement du passager")
    departure_time = models.DateTimeField(null=True, blank=True, help_text="Heure de départ du passager")
    arrival_time = models.DateTimeField(null=True, blank=True, help_text="Heure d'arrivée du passager")
    status = models.CharField(max_length=20, default='boarded')
    boarding_status = models.CharField(max_length=50, choices=BOARDING_STATUS_CHOICES, default='pending', help_text="Statut d'embarquement du passager")
    boarding_failure_reason = models.TextField(blank=True, default="", help_text="Raison de l'échec d'embarquement")

    ocp = models.ForeignKey(OperationalControlPlan, on_delete=models.SET_NULL, null=True, blank=True, help_text="Lien vers le plan OCP pour le trajet")

    created_at = models.DateTimeField(default=timezone.now, help_text="Date d'enregistrement de l'embarquement")
    updated_at = models.DateTimeField(default=timezone.now, help_text="Dernière mise à jour de l'enregistrement")

    # Nouveaux champs
    seat_number = models.CharField(max_length=10, blank=True, default="", help_text="Numéro de siège du passager")
    special_needs = models.TextField(blank=True, default="", help_text="Besoins spéciaux du passager")
    feedback = models.TextField(blank=True, default="", help_text="Retour d'expérience du passager")
    fare_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Tarif payé pour le voyage")

    def __str__(self):
        return f"{self.passenger.username} on Trip {self.trip.id}"

    class Meta:
        verbose_name = "Passenger Trip"
        verbose_name_plural = "Passenger Trips"
        unique_together = ('trip', 'passenger')

    def board_passenger(self):
        self.boarding_status = 'boarded'
        self.boarding_time = timezone.now()
        self.save()

    def fail_boarding(self, reason):
        self.boarding_status = 'boarding_failed'
        self.boarding_failure_reason = reason
        self.save()

    def disembark_passenger(self):
        self.boarding_status = 'off_board'
        self.arrival_time = timezone.now()
        self.save()

    def mark_no_show(self):
        self.boarding_status = 'no_show'
        self.save()

    def add_feedback(self, feedback_text):
        self.feedback = feedback_text
        self.save()

    def get_trip_duration(self):
        if self.arrival_time and self.departure_time:
            return self.arrival_time - self.departure_time
        return None

    def is_trip_completed(self):
        return self.boarding_status == 'off_board' and self.arrival_time is not None

    @classmethod
    def get_active_trips_for_passenger(cls, passenger):
        return cls.objects.filter(passenger=passenger, boarding_status='boarded')

    @classmethod
    def get_trip_history_for_passenger(cls, passenger):
        return cls.objects.filter(passenger=passenger).order_by('-created_at')

class Incident(models.Model):
    INCIDENT_TYPE_CHOICES = [
        ('accident', 'Accident'),
        ('delay', 'Delay'),
        ('mechanical_failure', 'Mechanical Failure'),
        ('passenger_complaint', 'Passenger Complaint'),
        ('other', 'Other'),
    ]
    
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='incidents')
    date = models.DateField(default=timezone.now)
    type = models.CharField(max_length=50, choices=INCIDENT_TYPE_CHOICES, default='other')
    description = models.TextField()
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reported_incidents')
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_details = models.TextField(blank=True, null=True)

    def mark_as_resolved(self, resolution_details=''):
        self.resolved = True
        self.resolved_at = timezone.now()
        self.resolution_details = resolution_details
        self.save()

    def __str__(self):
        return f"Incident on {self.date} during {self.trip} - {self.get_type_display()}"

    class Meta:
        verbose_name = "Incident"
        verbose_name_plural = "Incidents"
        ordering = ['-date']

class EventLog(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=100)
    timestamp = models.DateTimeField()
    description = models.TextField()
    ocp = models.ForeignKey(OperationalControlPlan, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.event_type} on {self.trip} at {self.timestamp}"
   
class TripStatus(models.Model):
    trip_status_id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, help_text="Lien vers le trajet concerné")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, help_text="Bus affecté au trajet")
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, help_text="Chauffeur affecté au trajet", null=True, blank=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ('ongoing', 'En cours'),
            ('completed', 'Terminé'),
            ('canceled', 'Annulé')
        ],
        default='ongoing'
    )
    breaks_completed = models.BooleanField(default=False, help_text="Indique si les pauses sont terminées")
    stops_completed = models.BooleanField(default=False, help_text="Indique si tous les arrêts sont effectués")
    incidents_resolved = models.BooleanField(default=False, help_text="Indique si tous les incidents sont résolus")
    updated_at = models.DateTimeField(default=timezone.now, help_text="Dernière mise à jour de l'état du trajet")
    created_at = models.DateTimeField(default=timezone.now, help_text="Date de création de l'état du trajet")
    ocp = models.ForeignKey(OperationalControlPlan, on_delete=models.SET_NULL, null=True, blank=True, help_text="Lien vers le plan de contrôle opérationnel")

    def __str__(self):
        return f"TripStatus {self.trip_status_id} - {self.status} - Trip {self.trip.id}"

    
    
class DisplaySchedule(models.Model):
    display_schedule_id = models.AutoField(primary_key=True, default='')
    bus_number = models.CharField(max_length=50, help_text="Numéro du bus", default='')
    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True)  # L'itinéraire emprunté
    departure_time = models.DateTimeField(help_text="Heure de départ")
    arrival_time = models.DateTimeField(help_text="Heure d’arrivée",)
    gate_number = models.CharField(max_length=50, help_text="Numéro de la porte",default='')
    seats_available = models.IntegerField(help_text="Nombre de places disponibles", default='')
    current_location = models.CharField(max_length=255, blank=True, null=True, help_text="Localisation actuelle du bus", default='')
    status = models.CharField(max_length=50, choices=[('on_time', 'À l’heure'), ('delayed', 'Retardé'), ('canceled', 'Annulé')], default='on_time')
    ocp_id = models.ForeignKey(OperationalControlPlan, on_delete=models.SET_NULL, null=True, help_text="Lien vers l'OCP")


class BusPosition(models.Model):
    position_id = models.AutoField(primary_key=True, default='')
    
    # Lien vers le véhicule (bus) dont on suit la position
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, help_text="Bus lié à cette position")

    # Coordonnées GPS
    latitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="Latitude en temps réel du bus",default='')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="Longitude en temps réel du bus", default='')
    
    # Vitesse et statut de mouvement
    speed = models.DecimalField(max_digits=5, decimal_places=2, help_text="Vitesse actuelle du bus (en km/h)",default='')
    is_moving = models.BooleanField(default=False, help_text="Le bus est-il en mouvement ?")
    
    # Timestamp de la position GPS
    timestamp = models.DateTimeField(default=timezone.now, help_text="Heure et date de la position GPS")

    # Lien vers l'OCP (optionnel) pour relier la position à un plan de contrôle opérationnel
    ocp_id = models.ForeignKey(OperationalControlPlan, on_delete=models.SET_NULL, null=True, help_text="Lien vers l'OCP, si applicable",default='')

    def __str__(self):
        return f"Bus {self.vehicle.vehicle_number} à {self.timestamp}"

    class Meta:
        verbose_name = "Bus Position"
        verbose_name_plural = "Bus Positions"
        ordering = ['-timestamp']  # Classe les positions par date décroissante
        
        
        
class BusTracking(models.Model):
    tracking_id = models.AutoField(primary_key=True, default='')
    
    # Lien vers le véhicule (bus)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, help_text="Bus suivi", default='')
    
    # Coordonnées GPS et vitesse
    latitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="Latitude en temps réel du bus",default='')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="Longitude en temps réel du bus",default='')
    speed = models.DecimalField(max_digits=5, decimal_places=2, help_text="Vitesse actuelle du bus (en km/h)",default='')
    
    # Source des données de localisation
    location_source = models.CharField(max_length=100, choices=[
        ('GPS', 'GPS'),
        ('Station', 'Station de Bus'),
        ('WiFi', 'Position via WiFi'),
        ('Manual', 'Entrée Manuelle')
    ], default='GPS', help_text="Source des informations de localisation")
    
    # Précision et qualité du signal
    accuracy = models.DecimalField(max_digits=5, decimal_places=2, help_text="Précision de la localisation (en mètres)", blank=True, null=True)
    
    # Statut du mouvement et batterie (utile pour certains systèmes GPS)
    is_moving = models.BooleanField(default=False, help_text="Le bus est-il en mouvement ?")
    battery_status = models.CharField(max_length=50, blank=True, null=True, help_text="Statut de la batterie du GPS ou système de suivi")
    
    # Timestamp de la position GPS
    timestamp = models.DateTimeField( help_text="Heure et date de la position GPS",default=timezone.now)
    
    def __str__(self):
        return f"Bus {self.vehicle.vehicle_number} - Source: {self.location_source} at {self.timestamp}"

    class Meta:
        verbose_name = "Bus Tracking"
        verbose_name_plural = "Bus Trackings"
        ordering = ['-timestamp']
        
        
class DriverNavigation(models.Model):
    navigation_id = models.AutoField(primary_key=True, default='')
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, help_text="Trajet lié à cette navigation")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, help_text="Véhicule associé",default='')
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, help_text="Chauffeur lié au trajet",default='')
    next_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, help_text="Prochain arrêt prévu",default='')
    directions = models.JSONField(help_text="Instructions GPS détaillées pour le chauffeur")
    current_latitude = models.DecimalField(default='',max_digits=9, decimal_places=6, help_text="Latitude actuelle du chauffeur")
    current_longitude = models.DecimalField(default='',max_digits=9, decimal_places=6, help_text="Longitude actuelle du chauffeur")
    estimated_arrival = models.DateTimeField(default=timezone.now, help_text="Heure estimée d'arrivée au prochain arrêt")
    updated_at = models.DateTimeField(default=timezone.now,  help_text="Dernière mise à jour de la navigation")
    ocp_id = models.ForeignKey(OperationalControlPlan, on_delete=models.SET_NULL, null=True, help_text="Lien vers l'OCP", default='')

    def __str__(self):
        return f"Driver {self.driver} - Trip {self.trip} Navigation"


    

class Reservation(models.Model):
    RESERVATION_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('cancelled', 'Annulée'),
        ('completed', 'Terminée'),
    ]

    RESERVATION_TYPE_CHOICES = [
        ('regular', 'Régulière'),
        ('special', 'Spéciale'),
        ('group', 'Groupe'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reservations')
    trip = models.ForeignKey('Trip', on_delete=models.CASCADE, related_name='reservations')
    boarding_stop = models.ForeignKey('Stop', on_delete=models.CASCADE, related_name='boarding_reservations')
    alighting_stop = models.ForeignKey('Stop', on_delete=models.CASCADE, related_name='alighting_reservations')
    
    reservation_date = models.DateTimeField()
    reservation_type = models.CharField(max_length=20, choices=RESERVATION_TYPE_CHOICES, default='regular')
    status = models.CharField(max_length=20, choices=RESERVATION_STATUS_CHOICES, default='pending')
    
    number_of_passengers = models.PositiveIntegerField(default=1)
    special_requirements = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    cancellation_reason = models.TextField(blank=True, null=True)
    cancellation_date = models.DateTimeField(blank=True, null=True)
    
    payment_status = models.CharField(max_length=20, default='pending')
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    confirmation_code = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ['-reservation_date']

    def __str__(self):
        return f"Reservation {self.confirmation_code} for {self.user.username} on {self.reservation_date}"

    def cancel_reservation(self, reason):
        self.status = 'cancelled'
        self.cancellation_reason = reason
        self.cancellation_date = timezone.now()
        self.save()

    def confirm_reservation(self):
        self.status = 'confirmed'
        self.save()

    def complete_reservation(self):
        self.status = 'completed'
        self.save()

    def is_cancellable(self):
        # Par exemple, on peut annuler jusqu'à 24h avant le départ
        return timezone.now() < (self.reservation_date - timezone.timedelta(hours=24))

    def generate_confirmation_code(self):
        # Logique pour générer un code de confirmation unique
        # Ceci est un exemple simple, vous voudrez peut-être utiliser quelque chose de plus robuste
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    def save(self, *args, **kwargs):
        if not self.confirmation_code:
            self.confirmation_code = self.generate_confirmation_code()
        super().save(*args, **kwargs)

    @property
    def is_upcoming(self):
        return self.reservation_date > timezone.now()

    @property
    def is_past(self):
        return self.reservation_date < timezone.now()
    
class PassengerTripHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    trip_date = models.DateTimeField(default=timezone.now)  # Date et heure du voyage
    origin = models.CharField(max_length=255, help_text="Lieu d'origine du voyage")
    destination = models.CharField(max_length=255, help_text="Destination du voyage")
    status = models.CharField(max_length=100, choices=[('completed', 'Complété'), ('canceled', 'Annulé')], default='completed')
    ocp_id = models.ForeignKey(OperationalControlPlan, on_delete=models.SET_NULL, null=True, blank=True, help_text="Lien vers le plan OCP", default='')

    def __str__(self):
        return f"{self.user.username} - Trip on {self.trip_date}"

    class Meta:
        verbose_name = "Passenger Trip History"
        verbose_name_plural = "Passenger Trip Histories"

class Transactionscan(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('nfc_physical', 'NFC Physical Card'),
        ('nfc_virtual', 'NFC Virtual (Phone)'),
        ('qr_code', 'QR Code'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    card = models.ForeignKey(CardInfo, on_delete=models.CASCADE)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, null=True, blank=True)
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPE_CHOICES)
    timestamp = models.DateTimeField(default=timezone.now)
    is_successful = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Transaction by {self.user.username} on {self.timestamp}"
    

