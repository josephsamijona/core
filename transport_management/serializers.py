# transport_api/serializers.py
from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth import get_user_model
from inventory_management.models import Vehicle
from .models import (
    OperationalRule, RuleExecution, RuleParameter, RuleSet, RuleSetMembership,
    Destination, Route, Stop, RouteStop, Schedule, ScheduleException,
    ResourceAvailability, Driver
)
User = get_user_model()

class OperationalRuleSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = OperationalRule
        fields = '__all__'

class RuleExecutionSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = RuleExecution
        fields = '__all__'

class RuleParameterSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = RuleParameter
        fields = '__all__'

class RuleSetSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = RuleSet
        fields = '__all__'

class DestinationSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = '__all__'

class RouteSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = '__all__'

class StopSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = '__all__'

class RouteStopSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = RouteStop
        fields = '__all__'

class ScheduleSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = '__all__'

class ScheduleExceptionSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = ScheduleException
        fields = '__all__'

class ResourceAvailabilitySerializercrud(serializers.ModelSerializer):
    class Meta:
        model = ResourceAvailability
        fields = '__all__'

class DriverSerializercrud(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = '__all__'

class PeakHoursField(serializers.JSONField):
    def to_internal_value(self, data):
        # Validation personnalisée pour les heures de pointe
        if not isinstance(data, dict):
            raise serializers.ValidationError("Le format des heures de pointe doit être un dictionnaire.")
        # Vous pouvez ajouter des validations supplémentaires ici
        return super().to_internal_value(data)

    def to_representation(self, value):
        return super().to_representation(value)

class DestinationSerializer(serializers.ModelSerializer):
    peak_hours = PeakHoursField()
    facilities_available = serializers.JSONField()
    accessibility_features = serializers.JSONField()

    class Meta:
        model = Destination
        fields = [
            'id', 'name', 'locality', 'zone_code', 'circuit',
            'address', 'latitude', 'longitude', 'gps_coordinates',
            'category', 'destination_type', 'description',
            'facilities_available', 'accessibility_features',
            'parking_available', 'is_accessible',
            'peak_hours', 'estimated_daily_traffic',
            'recommended_visit_times', 'service_hours',
            'emergency_contact', 'support_phone', 'email',
            'is_active', 'created_at', 'updated_at', 'created_by',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        return super().create(validated_data)

    def validate_estimated_daily_traffic(self, value):
        if value < 0:
            raise serializers.ValidationError("Le trafic quotidien estimé doit être positif.")
        return value

    def validate(self, data):
        # Validation pour s'assurer que les coordonnées GPS sont présentes
        if not data.get('latitude') or not data.get('longitude'):
            raise serializers.ValidationError("Les champs latitude et longitude sont requis.")
        return data
    


class DestinationitinineraireSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = ['id', 'name', 'latitude', 'longitude']

class RouteitinineraireSerializer(serializers.ModelSerializer):
    destinations = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Destination.objects.all()
    )
    alternate_routes = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Route.objects.all(),
        required=False
    )

    class Meta:
        model = Route
        fields = [
            'id', 'name', 'description', 'route_code', 'circuit',
            'destinations', 'alternate_routes',
            'route_category', 'difficulty_level', 'type',
            'direction', 'total_distance', 'estimated_duration',
            'service_hours', 'operating_days',
            'peak_frequency', 'off_peak_frequency', 'weekend_frequency',
            'path', 'route_color', 'traffic_conditions', 'elevation_profile',
            'vehicle_type_restrictions', 'weather_restrictions', 'seasonal_variations',
            'status', 'is_active', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'total_distance', 'estimated_duration', 'created_at', 'updated_at', 'created_by']

    def create(self, validated_data):
        user = self.context['request'].user
        destinations_data = validated_data.pop('destinations', [])
        alternate_routes_data = validated_data.pop('alternate_routes', [])
        route = Route.objects.create(created_by=user, **validated_data)
        route.destinations.set(destinations_data)
        route.alternate_routes.set(alternate_routes_data)
        route.calculate_metrics()
        route.save()
        return route

    def update(self, instance, validated_data):
        destinations_data = validated_data.pop('destinations', None)
        alternate_routes_data = validated_data.pop('alternate_routes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if destinations_data is not None:
            instance.destinations.set(destinations_data)
        if alternate_routes_data is not None:
            instance.alternate_routes.set(alternate_routes_data)
        instance.calculate_metrics()
        instance.save()
        return instance


class StoparretSerializer(serializers.ModelSerializer):
    accessibility_features = serializers.JSONField()
    facilities = serializers.JSONField()
    amenities = serializers.JSONField()

    class Meta:
        model = Stop
        fields = [
            'id', 'name', 'stop_code', 'description',
            'latitude', 'longitude', 'address', 'service_zone',
            'platform_number', 'zone_code',
            'stop_type', 'shelter_available', 'lighting_available',
            'seating_capacity', 'accessibility_features', 'facilities', 'amenities',
            'peak_hours_capacity', 'average_waiting_time',
            'boarding_type', 'security_features',
            'maintenance_schedule', 'last_inspection_date', 'next_maintenance_date',
            'is_active', 'status', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        return super().create(validated_data)

    def validate_average_waiting_time(self, value):
        if value < 0:
            raise serializers.ValidationError("Le temps d'attente moyen doit être positif.")
        return value
    
class RouteStoparretSerializer(serializers.ModelSerializer):
    route = serializers.PrimaryKeyRelatedField(queryset=Route.objects.all())
    stop = serializers.PrimaryKeyRelatedField(queryset=Stop.objects.all())

    class Meta:
        model = RouteStop
        fields = [
            'id', 'route', 'stop', 'order', 'stop_sequence',
            'distance_from_start', 'estimated_time', 'dwell_time',
            'is_timepoint', 'stop_announcement', 'passenger_exchange',
            'stop_restrictions', 'pickup_type', 'drop_off_type',
            'connection_routes', 'transfer_time',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        if data['order'] <= 0:
            raise serializers.ValidationError("L'ordre doit être un entier positif.")
        if data['estimated_time'] < 0:
            raise serializers.ValidationError("Le temps estimé doit être positif.")
        return data
    
class ScheduleautomatSerializer(serializers.ModelSerializer):
    route = serializers.PrimaryKeyRelatedField(queryset=Route.objects.all())
    timepoints = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = Schedule
        fields = '__all__'
        read_only_fields = ['id', 'is_approved', 'approval_date', 'approved_by', 'created_at', 'updated_at', 'created_by', 'timepoints']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        schedule = super().create(validated_data)
        # Générer les horaires pour la plage de dates
        schedule.generate_timepoints_for_date(timezone.now().date())
        return schedule

    def update(self, instance, validated_data):
        schedule = super().update(instance, validated_data)
        # Régénérer les horaires si les paramètres ont changé
        schedule.generate_timepoints_for_date(timezone.now().date())
        return schedule

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("L'heure de fin doit être après l'heure de début.")
        if data['frequency'] <= 0:
            raise serializers.ValidationError("La fréquence doit être positive.")
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("La date de début doit être avant la date de fin.")
        return data
class ScheduleautomatSerializer(serializers.ModelSerializer):
    validation_history = serializers.JSONField(read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)
    current_status = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Schedule
        fields = [
            'id', 'route', 'route_name', 'schedule_code', 'schedule_version',
            'season', 'day_of_week', 'start_date', 'end_date',
            'holiday_schedule', 'start_time', 'end_time', 'frequency',
            'rush_hour_adjustment', 'minimum_layover',
            'weather_adjustment', 'special_event_adjustment',
            'peak_hours_frequency', 'off_peak_frequency',
            'is_active', 'is_approved', 'approval_date', 'approved_by',
            'notes', 'timepoints', 'created_at', 'updated_at', 'created_by',
            'status', 'is_current_version', 'validation_history',
            'activation_date', 'current_status'
        ]
        read_only_fields = [
            'id', 'is_approved', 'approval_date', 'approved_by',
            'created_at', 'updated_at', 'created_by', 'timepoints',
            'validation_history', 'is_current_version', 'activation_date'
        ]

    def validate(self, data):
        if data.get('start_time') >= data.get('end_time'):
            raise serializers.ValidationError("L'heure de fin doit être après l'heure de début.")
        if data.get('frequency', 0) <= 0:
            raise serializers.ValidationError("La fréquence doit être positive.")
        if data.get('start_date') > data.get('end_date'):
            raise serializers.ValidationError("La date de début doit être avant la date de fin.")
        return data

class DriverSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    preferred_routes = serializers.PrimaryKeyRelatedField(many=True, queryset=Route.objects.all(), required=False)
    certifications = serializers.JSONField(required=False)
    incident_history = serializers.JSONField(required=False)
    performance_metrics = serializers.JSONField(required=False)
    route_restrictions = serializers.JSONField(required=False)
    break_preferences = serializers.JSONField(required=False)
    training_records = serializers.JSONField(required=False)
    special_skills = serializers.JSONField(required=False)
    language_skills = serializers.JSONField(required=False)
    notes = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = Driver
        fields = [
            'id', 'user', 'employee_id', 'first_name', 'last_name', 'date_of_birth',
            'phone_number', 'emergency_contact', 'address', 'email',
            'license_number', 'license_type', 'license_expiry_date', 'experience_years',
            'certifications', 'employment_status', 'availability_status',
            'rating', 'total_trips', 'total_hours', 'incident_history', 'performance_metrics',
            'preferred_routes', 'route_restrictions', 'maximum_hours_per_week', 'break_preferences',
            'training_records', 'special_skills', 'language_skills',
            'created_at', 'updated_at', 'last_medical_check', 'next_medical_check', 'notes'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_trips', 'total_hours', 'performance_metrics']

    def validate_license_expiry_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("La date d'expiration du permis doit être dans le futur.")
        return value

    def validate_email(self, value):
        if Driver.objects.filter(email=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Un chauffeur avec cet e-mail existe déjà.")
        return value

    def create(self, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user = User.objects.get(pk=user_data.id)
        else:
            # Créer un nouvel utilisateur si nécessaire
            user = User.objects.create_user(
                username=validated_data['email'],
                email=validated_data['email'],
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name']
            )
        validated_data['user'] = user
        driver = Driver.objects.create(**validated_data)
        return driver

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user = User.objects.get(pk=user_data.id)
            instance.user = user
        # Mettre à jour les champs du chauffeur
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = ['id', 'first_name', 'last_name', 'employee_id']

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id', 'vehicle_number', 'model', 'license_plate']

class ResourceAvailabilitySerializer(serializers.ModelSerializer):
    driver = DriverSerializer(required=False, allow_null=True)
    vehicle = VehicleSerializer(required=False, allow_null=True)
    restrictions = serializers.JSONField(required=False)
    conditions = serializers.JSONField(required=False)
    reason = serializers.CharField(allow_blank=True, required=False)
    notes = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = ResourceAvailability
        fields = [
            'id', 'resource_type', 'driver', 'vehicle', 'date', 'start_time', 'end_time',
            'is_available', 'capacity_percentage', 'status', 'restrictions', 'conditions',
            'priority_level', 'reason', 'notes', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def validate(self, data):
        # Validation pour s'assurer qu'un seul type de ressource est spécifié
        if data.get('driver') and data.get('vehicle'):
            raise serializers.ValidationError("Vous ne pouvez pas spécifier à la fois un chauffeur et un véhicule.")
        if not data.get('driver') and not data.get('vehicle'):
            raise serializers.ValidationError("Vous devez spécifier un chauffeur ou un véhicule.")
        # Validation pour s'assurer que les heures sont cohérentes
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("L'heure de fin doit être après l'heure de début.")
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        # Gestion des relations imbriquées
        driver_data = validated_data.pop('driver', None)
        vehicle_data = validated_data.pop('vehicle', None)
        if driver_data:
            driver = Driver.objects.get(pk=driver_data['id'])
            validated_data['driver'] = driver
        if vehicle_data:
            vehicle = Vehicle.objects.get(pk=vehicle_data['id'])
            validated_data['vehicle'] = vehicle
        resource_availability = ResourceAvailability.objects.create(**validated_data)
        return resource_availability

    def update(self, instance, validated_data):
        driver_data = validated_data.pop('driver', None)
        vehicle_data = validated_data.pop('vehicle', None)
        if driver_data:
            driver = Driver.objects.get(pk=driver_data['id'])
            instance.driver = driver
            instance.vehicle = None
        elif vehicle_data:
            vehicle = Vehicle.objects.get(pk=vehicle_data['id'])
            instance.vehicle = vehicle
            instance.driver = None
        else:
            instance.driver = None
            instance.vehicle = None
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    