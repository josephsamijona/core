from django.contrib import admin
from django.db import models 
from .models import (
    OperationalRule, RuleExecution, RuleParameter, RuleSet, RuleSetMembership,
    Destination, Route, Stop, RouteStop, Schedule, ScheduleException, ResourceAvailability,
    Driver, DriverSchedule, DriverVehicleAssignment, Trip, PassengerTrip, Incident,
    EventLog, TripStatus, DisplaySchedule, BusPosition, BusTracking, DriverNavigation,
    PassengerTripHistory, TransactionScan
)
from inventory_management.models import Vehicle
from django.contrib.auth import get_user_model
from django_json_widget.widgets import JSONEditorWidget
from django.contrib.admin import widgets as admin_widgets
from django import forms

User = get_user_model()

# Inline for RuleParameter in OperationalRule
class RuleParameterInline(admin.TabularInline):
    model = RuleParameter
    extra = 1

@admin.register(OperationalRule)
class OperationalRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'rule_type', 'is_active', 'priority', 'created_at')
    list_filter = ('rule_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('priority', 'rule_type', 'name')
    inlines = [RuleParameterInline]

@admin.register(RuleExecution)
class RuleExecutionAdmin(admin.ModelAdmin):
    list_display = ('rule', 'executed_at', 'success')
    list_filter = ('success', 'executed_at')
    search_fields = ('rule__name',)
    date_hierarchy = 'executed_at'

@admin.register(RuleParameter)
class RuleParameterAdmin(admin.ModelAdmin):
    list_display = ('name', 'rule', 'parameter_type', 'default_value')
    list_filter = ('parameter_type',)
    search_fields = ('name', 'rule__name', 'description')

# Inline for RuleSetMembership in RuleSet
class RuleSetMembershipInline(admin.TabularInline):
    model = RuleSetMembership
    extra = 1

@admin.register(RuleSet)
class RuleSetAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    inlines = [RuleSetMembershipInline]

@admin.register(RuleSetMembership)
class RuleSetMembershipAdmin(admin.ModelAdmin):
    list_display = ('rule_set', 'rule', 'order')
    list_filter = ('rule_set',)
    ordering = ('rule_set', 'order')
    search_fields = ('rule_set__name', 'rule__name')

@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ('name', 'locality', 'zone_code', 'category', 'is_active')
    list_filter = ('locality', 'category', 'is_active', 'created_at')
    search_fields = ('name', 'locality', 'address', 'description')
    ordering = ('name', 'locality')

# Inline for RouteStop in Route
class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 1

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'route_code', 'route_category', 'status', 'is_active')
    list_filter = ('route_category', 'status', 'is_active', 'created_at')
    search_fields = ('name', 'route_code', 'description')
    ordering = ('name',)
    inlines = [RouteStopInline]

@admin.register(Stop)
class StopAdmin(admin.ModelAdmin):
    list_display = ('name', 'stop_code', 'stop_type', 'service_zone', 'status', 'is_active')
    list_filter = ('stop_type', 'service_zone', 'status', 'is_active', 'created_at')
    search_fields = ('name', 'stop_code', 'address', 'description')
    ordering = ('name',)

@admin.register(RouteStop)
class RouteStopAdmin(admin.ModelAdmin):
    list_display = ('route', 'stop', 'order', 'stop_sequence')
    list_filter = ('route', 'stop')
    ordering = ('route', 'order')
    search_fields = ('route__name', 'stop__name')

class ScheduleExceptionInline(admin.TabularInline):
    model = ScheduleException
    extra = 1

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('route', 'day_of_week', 'start_time', 'end_time', 'status', 'is_active')
    list_filter = ('route', 'day_of_week', 'status', 'is_active', 'created_at')
    search_fields = ('route__name', 'schedule_code', 'schedule_version', 'notes')
    ordering = ('route', 'day_of_week', 'start_time')
    inlines = [ScheduleExceptionInline]
    readonly_fields = ('created_at', 'updated_at', 'approval_date', 'activation_date')

    fieldsets = (
        ('Identification', {
            'fields': ('route', 'schedule_code', 'schedule_version', 'season', 'status', 'is_active')
        }),
        ('Période', {
            'fields': ('day_of_week', ('start_date', 'end_date'), 'holiday_schedule')
        }),
        ('Horaires', {
            'fields': (('start_time', 'end_time'), 'frequency', ('peak_hours_frequency', 'off_peak_frequency'),
                       'rush_hour_adjustment', 'minimum_layover')
        }),
        ('Ajustements', {
            'fields': ('weather_adjustment', 'special_event_adjustment')
        }),
        ('Gestion des trips', {
            'fields': ('trip_template', 'schedule_metrics', 'resource_requirements')
        }),
        ('Validation', {
            'fields': ('is_approved', 'approved_by', 'approval_date', 'is_current_version', 'validation_history')
        }),
        ('Métadonnées', {
            'fields': ('notes', 'timepoints', 'created_at', 'updated_at', 'created_by')
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('route', 'schedule_code', 'schedule_version', 'created_by')
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.save()

@admin.register(ScheduleException)
class ScheduleExceptionAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'exception_date', 'exception_type', 'is_cancelled', 'impact_level')
    list_filter = ('exception_type', 'is_cancelled', 'impact_level', 'exception_date')
    search_fields = ('schedule__route__name', 'reason', 'alternative_service')
    ordering = ('exception_date',)
    filter_horizontal = ('affected_routes',)

    fieldsets = (
        (None, {
            'fields': ('schedule', 'exception_date', 'exception_type', 'reason', 'impact_level')
        }),
        ('Horaires modifiés', {
            'fields': (('start_time', 'end_time'), 'modified_frequency')
        }),
        ('Statuts', {
            'fields': ('is_cancelled', 'is_modified', 'requires_approval', 'notification_sent')
        }),
        ('Détails', {
            'fields': ('alternative_service', 'affected_routes')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at', 'created_by')
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.save()

@admin.register(ResourceAvailability)
class ResourceAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('resource_type', 'get_resource', 'date', 'start_time', 'end_time', 'is_available', 'status')
    list_filter = ('resource_type', 'is_available', 'status', 'date')
    search_fields = ('driver__name', 'vehicle__license_plate', 'reason', 'notes')
    ordering = ('date', 'start_time')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Type de ressource', {
            'fields': ('resource_type', 'driver', 'vehicle')
        }),
        ('Période de disponibilité', {
            'fields': ('date', 'start_time', 'end_time')
        }),
        ('Statut et capacité', {
            'fields': ('is_available', 'capacity_percentage', 'status')
        }),
        ('Restrictions et conditions', {
            'fields': ('restrictions', 'conditions', 'priority_level')
        }),
        ('Raison et commentaires', {
            'fields': ('reason', 'notes')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at', 'created_by')
        }),
    )

    def get_resource(self, obj):
        return obj.driver or obj.vehicle
    get_resource.short_description = 'Ressource'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.save()
        
        
class DriverScheduleInline(admin.TabularInline):
    model = DriverSchedule
    extra = 0
    fields = ('shift_start', 'shift_end', 'status', 'is_active')
    readonly_fields = ('created_at', 'updated_at')
    show_change_link = True

class DriverVehicleAssignmentInline(admin.TabularInline):
    model = DriverVehicleAssignment
    extra = 0
    fields = ('vehicle', 'assigned_from', 'assigned_until', 'status')
    readonly_fields = ('created_at', 'updated_at')
    show_change_link = True

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'first_name', 'last_name', 'license_number', 'employment_status', 'availability_status')
    list_filter = ('employment_status', 'availability_status', 'license_type')
    search_fields = ('first_name', 'last_name', 'employee_id', 'license_number', 'email', 'phone_number')
    ordering = ('last_name', 'first_name')
    readonly_fields = ('created_at', 'updated_at', 'total_trips', 'total_hours', 'rating')
    filter_horizontal = ('preferred_routes',)
    inlines = [DriverScheduleInline, DriverVehicleAssignmentInline]

    fieldsets = (
        ('Informations personnelles', {
            'fields': ('user', 'employee_id', ('first_name', 'last_name'), 'date_of_birth', 'email')
        }),
        ('Contact', {
            'fields': ('phone_number', 'emergency_contact', 'address')
        }),
        ('Qualifications', {
            'fields': (('license_number', 'license_type'), 'license_expiry_date', 'experience_years', 'certifications')
        }),
        ('Statut et disponibilité', {
            'fields': ('employment_status', 'availability_status')
        }),
        ('Performance et historique', {
            'fields': ('rating', 'total_trips', 'total_hours', 'incident_history', 'performance_metrics')
        }),
        ('Préférences et restrictions', {
            'fields': ('preferred_routes', 'route_restrictions', 'maximum_hours_per_week', 'break_preferences')
        }),
        ('Formation et compétences', {
            'fields': ('training_records', 'special_skills', 'language_skills')
        }),
        ('Santé', {
            'fields': ('last_medical_check', 'next_medical_check')
        }),
        ('Métadonnées', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.save()

@admin.register(DriverSchedule)
class DriverScheduleAdmin(admin.ModelAdmin):
    list_display = ('driver', 'shift_start', 'shift_end', 'status', 'is_active', 'priority')
    list_filter = ('status', 'is_active', 'priority', 'driver')
    search_fields = ('driver__first_name', 'driver__last_name', 'notes')
    ordering = ('-shift_start', 'priority')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'shift_start'

    fieldsets = (
        ('Relations de base', {
            'fields': ('driver', 'rule_set')
        }),
        ('Informations temporelles', {
            'fields': (('shift_start', 'shift_end'), ('actual_start_time', 'actual_end_time'))
        }),
        ('Gestion des pauses et repos', {
            'fields': ('breaks_scheduled', 'rest_time_between_shifts')
        }),
        ('Statuts et contrôles', {
            'fields': ('status', 'is_active', 'priority')
        }),
        ('Validation et conformité', {
            'fields': ('validation_status', 'compliance_notes', 'rule_violations')
        }),
        ('Modifications et historique', {
            'fields': ('modification_history', 'modified_by', 'modification_reason')
        }),
        ('Métadonnées', {
            'fields': ('notes', 'created_at', 'updated_at', 'created_by')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.modified_by = request.user
        obj.save()

@admin.register(DriverVehicleAssignment)
class DriverVehicleAssignmentAdmin(admin.ModelAdmin):
    list_display = ('driver', 'vehicle', 'assigned_from', 'assigned_until', 'status', 'priority')
    list_filter = ('status', 'priority', 'assignment_type', 'driver', 'vehicle')
    search_fields = ('driver__first_name', 'driver__last_name', 'vehicle__license_plate', 'notes')
    ordering = ('-assigned_from', 'priority')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'assigned_from'

    fieldsets = (
        ('Relations principales', {
            'fields': ('driver', 'vehicle', 'rule_set')
        }),
        ('Informations temporelles', {
            'fields': (('assigned_from', 'assigned_until'), ('actual_start', 'actual_end'))
        }),
        ('Caractéristiques de l\'affectation', {
            'fields': ('assignment_type', 'priority', 'status')
        }),
        ('Validation et conformité', {
            'fields': ('validation_status', 'rule_violations', 'compliance_checks')
        }),
        ('Suivi des modifications', {
            'fields': ('modification_history', 'modified_by', 'modification_reason')
        }),
        ('Métadonnées', {
            'fields': ('notes', 'created_at', 'updated_at', 'created_by')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.modified_by = request.user
        obj.save()
        
class PassengerTripInline(admin.TabularInline):
    model = PassengerTrip
    extra = 0
    fields = ('passenger', 'boarding_stop', 'alighting_stop', 'status', 'boarding_status', 'payment_status')
    readonly_fields = ('check_in_time', 'boarding_time', 'departure_time', 'arrival_time')
    show_change_link = True

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('id', 'trip_date', 'route', 'driver', 'vehicle', 'status', 'priority')
    list_filter = ('status', 'priority', 'trip_date', 'route', 'driver', 'vehicle')
    search_fields = ('route__name', 'driver__first_name', 'driver__last_name', 'vehicle__license_plate', 'notes')
    ordering = ('-trip_date', 'priority')
    readonly_fields = ('created_at', 'updated_at', 'departure_time', 'arrival_time', 'actual_start_time', 'actual_end_time')
    date_hierarchy = 'trip_date'
    inlines = [PassengerTripInline]

    fieldsets = (
        ('Relations principales', {
            'fields': ('schedule', 'destination', 'route', 'driver', 'vehicle', 'rule_set')
        }),
        ('Informations temporelles', {
            'fields': ('trip_date', ('planned_departure', 'planned_arrival'), ('departure_time', 'arrival_time'), ('actual_start_time', 'actual_end_time'))
        }),
        ('Caractéristiques du voyage', {
            'fields': ('origin', 'passenger_count', 'max_capacity', 'trip_type', 'priority')
        }),
        ('Statut et suivi', {
            'fields': ('status', 'delay_duration', 'real_time_incidents', 'weather_conditions', 'traffic_conditions')
        }),
        ('Validation et conformité', {
            'fields': ('validation_status', 'rule_violations', 'safety_checks')
        }),
        ('Suivi des modifications', {
            'fields': ('modification_history', 'modified_by', 'modification_reason')
        }),
        ('Métadonnées', {
            'fields': ('notes', 'created_at', 'updated_at', 'created_by')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.modified_by = request.user
        obj.save()

@admin.register(PassengerTrip)
class PassengerTripAdmin(admin.ModelAdmin):
    list_display = ('trip', 'passenger', 'boarding_stop', 'alighting_stop', 'boarding_status', 'payment_status')
    list_filter = ('boarding_status', 'payment_status', 'passenger_type', 'status')
    search_fields = ('passenger__username', 'passenger__first_name', 'passenger__last_name', 'ticket_number', 'notes')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'check_in_time', 'boarding_time', 'departure_time', 'arrival_time')

    fieldsets = (
        ('Relations principales', {
            'fields': ('trip', 'passenger', 'boarding_stop', 'alighting_stop', 'rule_set')
        }),
        ('Informations temporelles', {
            'fields': (('check_in_time', 'boarding_time'), ('departure_time', 'arrival_time'))
        }),
        ('Statuts', {
            'fields': ('status', 'boarding_status', 'passenger_type', 'payment_status')
        }),
        ('Informations de voyage', {
            'fields': ('seat_number', 'special_needs', 'luggage_info', 'fare_paid', 'ticket_number')
        }),
        ('Validation et conformité', {
            'fields': ('validation_status', 'rule_violations', 'boarding_failure_reason')
        }),
        ('Retour d\'expérience', {
            'fields': ('feedback', 'satisfaction_rating', 'incident_reports')
        }),
        ('Historique et modifications', {
            'fields': ('modification_history', 'modified_by')
        }),
        ('Métadonnées', {
            'fields': ('notes', 'created_at', 'updated_at', 'created_by')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.modified_by = request.user
        obj.save()

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('incident_id', 'type', 'severity', 'priority', 'date', 'status', 'resolved')
    list_filter = ('type', 'severity', 'priority', 'status', 'resolved', 'date')
    search_fields = ('incident_id', 'description', 'trip__id', 'reported_by__username', 'assigned_to__username', 'notes')
    ordering = ('-date', 'priority')
    readonly_fields = ('created_at', 'updated_at', 'resolved_at')

    fieldsets = (
        ('Relations principales', {
            'fields': ('trip', 'reported_by', 'assigned_to', 'rule_set')
        }),
        ('Informations de base', {
            'fields': ('incident_id', 'type', 'severity', 'priority', 'date', 'location')
        }),
        ('Description et détails', {
            'fields': ('description', 'detailed_report', 'affected_assets', 'witnesses', 'evidence')
        }),
        ('Statut et résolution', {
            'fields': ('status', 'resolved', 'resolved_at', 'resolution_details', 'resolution_cost')
        }),
        ('Suivi et validation', {
            'fields': ('validation_status', 'rule_violations', 'follow_up_actions', 'preventive_measures')
        }),
        ('Historique et modifications', {
            'fields': ('modification_history', 'modified_by')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at', 'created_by')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.modified_by = request.user
        obj.save()
        
class JSONFieldModelAdminForm(forms.ModelForm):
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

# Enregistrement du modèle EventLog
@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'event_type', 'severity', 'trip', 'timestamp', 'processed')
    list_filter = ('event_type', 'severity', 'processed', 'processing_status', 'timestamp')
    search_fields = ('event_id', 'description', 'trip__id', 'trip__route__name', 'created_by__username')
    ordering = ('-timestamp',)
    readonly_fields = ('event_id', 'created_at', 'updated_at')
    date_hierarchy = 'timestamp'
    form = JSONFieldModelAdminForm

    fieldsets = (
        ('Informations de base', {
            'fields': ('event_id', 'event_type', 'severity', 'description', 'trip', 'rule_set', 'created_by')
        }),
        ('Détails de l\'événement', {
            'fields': ('event_data', 'location_data', 'related_entities', 'context_data')
        }),
        ('Traitement et suivi', {
            'fields': ('processed', 'processing_status', 'processing_details', 'requires_action', 'action_taken')
        }),
        ('Validation et conformité', {
            'fields': ('validation_status', 'rule_violations')
        }),
        ('Métadonnées', {
            'fields': ('timestamp', 'created_at', 'updated_at', 'source', 'ip_address', 'user_agent')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.save()

# Enregistrement du modèle TripStatus
@admin.register(TripStatus)
class TripStatusAdmin(admin.ModelAdmin):
    list_display = ('trip', 'status', 'stage', 'progress_percentage', 'updated_at')
    list_filter = ('status', 'stage', 'trip__route__name', 'vehicle', 'driver')
    search_fields = ('trip__id', 'trip__route__name', 'vehicle__vehicle_number', 'driver__first_name', 'driver__last_name')
    ordering = ('-updated_at',)
    readonly_fields = ('created_at', 'updated_at')
    form = JSONFieldModelAdminForm

    fieldsets = (
        ('Identifiants et relations', {
            'fields': ('trip', 'vehicle', 'driver', 'rule_set')
        }),
        ('Statut général', {
            'fields': ('status', 'stage', 'progress_percentage')
        }),
        ('Suivi des arrêts et pauses', {
            'fields': ('breaks_status', 'breaks_completed', 'stops_status', 'stops_completed', 'next_stop')
        }),
        ('Suivi des incidents', {
            'fields': ('incidents_status', 'incidents_resolved', 'active_incidents')
        }),
        ('Métriques de performance', {
            'fields': ('delay_duration', 'estimated_completion_time', 'performance_metrics')
        }),
        ('Validation et conformité', {
            'fields': ('validation_status', 'rule_violations', 'safety_checks')
        }),
        ('Suivi des modifications', {
            'fields': ('modification_history', 'modified_by')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.modified_by = request.user
        obj.save()

# Enregistrement du modèle DisplaySchedule
@admin.register(DisplaySchedule)
class DisplayScheduleAdmin(admin.ModelAdmin):
    list_display = ('bus_number', 'trip', 'scheduled_departure', 'status', 'display_priority')
    list_filter = ('status', 'display_priority', 'scheduled_departure', 'trip__route__name')
    search_fields = ('bus_number', 'trip__id', 'trip__route__name', 'status_message')
    ordering = ('display_order', 'scheduled_departure')
    readonly_fields = ('created_at', 'updated_at', 'last_refresh')
    date_hierarchy = 'scheduled_departure'
    form = JSONFieldModelAdminForm

    fieldsets = (
        ('Informations de base', {
            'fields': ('bus_number', 'trip', 'rule_set', 'display_order', 'display_priority')
        }),
        ('Horaires', {
            'fields': (('scheduled_departure', 'estimated_departure'), ('scheduled_arrival', 'estimated_arrival'))
        }),
        ('Localisation', {
            'fields': ('gate_number', 'platform', 'terminal', 'current_location', 'location_coordinates', 'next_stop')
        }),
        ('Capacité', {
            'fields': ('seats_available', 'seats_reserved')
        }),
        ('Statut et notifications', {
            'fields': ('status', 'delay_duration', 'status_message', 'announcements')
        }),
        ('Validation et suivi', {
            'fields': ('validation_status', 'display_rules', 'display_history')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at', 'last_refresh', 'modified_by')
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.modified_by = request.user
        obj.save()

# Enregistrement du modèle BusPosition

# Enregistrement du modèle BusTracking@admin.register(BusPosition)
class BusPositionAdmin(admin.ModelAdmin):
    list_display = ('trip', 'timestamp', 'latitude', 'longitude', 'speed', 'is_moving')
    list_filter = ('position_status', 'is_moving', 'timestamp')
    search_fields = ('trip__id', 'trip__route__name', 'trip__vehicle__vehicle_number')
    ordering = ('-timestamp',)
    readonly_fields = ('recorded_at',)  # Correction ici : Remplacer 'created_at' par 'recorded_at'
    date_hierarchy = 'timestamp'
    form = JSONFieldModelAdminForm

    fieldsets = (
        ('Identification', {
            'fields': ('trip', 'rule_set')
        }),
        ('Coordonnées GPS', {
            'fields': ('latitude', 'longitude', 'altitude')
        }),
        ('Informations de mouvement', {
            'fields': ('speed', 'heading', 'is_moving')
        }),
        ('Qualité et statut', {
            'fields': ('position_status', 'accuracy', 'hdop', 'is_valid')
        }),
        ('Horodatage', {
            'fields': ('timestamp', 'recorded_at')
        }),
        ('Données brutes', {
            'fields': ('data_source', 'raw_data')
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.save()

# Enregistrement du modèle DriverNavigation
@admin.register(DriverNavigation)
class DriverNavigationAdmin(admin.ModelAdmin):
    list_display = ('trip', 'navigation_provider', 'navigation_status', 'estimated_arrival')
    list_filter = ('navigation_provider', 'navigation_status', 'route_type')
    search_fields = ('trip__id', 'trip__route__name', 'driver__first_name', 'driver__last_name')
    ordering = ('-updated_at',)
    readonly_fields = ('created_at', 'updated_at', 'last_sync')
    date_hierarchy = 'created_at'
    form = JSONFieldModelAdminForm

    fieldsets = (
        ('Identification', {
            'fields': ('trip', 'rule_set', 'navigation_provider', 'provider_settings', 'route_type')
        }),
        ('Statut et progression', {
            'fields': ('navigation_status', 'next_stop')
        }),
        ('Instructions et itinéraire', {
            'fields': ('route_details', 'current_step', 'remaining_steps')
        }),
        ('Estimations', {
            'fields': ('estimated_arrival', 'estimated_duration', 'estimated_distance')
        }),
        ('Alertes et notifications', {
            'fields': ('alerts', 'traffic_info')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at', 'last_sync')
        }),
    )

# Enregistrement du modèle PassengerTripHistory
@admin.register(PassengerTripHistory)
class PassengerTripHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'trip', 'trip_date', 'status', 'satisfaction_rating')
    list_filter = ('status', 'satisfaction_rating', 'trip_date')
    search_fields = ('user__username', 'trip__id', 'trip__route__name', 'origin_stop__name', 'destination_stop__name')
    ordering = ('-trip_date',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'trip_date'
    form = JSONFieldModelAdminForm

    fieldsets = (
        ('Relations principales', {
            'fields': ('user', 'trip')
        }),
        ('Informations du voyage', {
            'fields': ('trip_date', 'boarding_time', 'alighting_time')
        }),
        ('Points de départ et d\'arrivée', {
            'fields': ('origin_stop', 'destination_stop')
        }),
        ('Statut et détails du voyage', {
            'fields': ('status', 'status_details')
        }),
        ('Tarification et paiement', {
            'fields': ('fare_paid', 'payment_method', 'refund_status')
        }),
        ('Retour d\'expérience', {
            'fields': ('satisfaction_rating', 'feedback', 'reported_issues')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at', 'modification_history')
        }),
    )

# Enregistrement du modèle TransactionScan
@admin.register(TransactionScan)
class TransactionScanAdmin(admin.ModelAdmin):
    list_display = ('scan_id', 'user', 'card', 'scan_type', 'scan_status', 'timestamp')
    list_filter = ('scan_type', 'scan_status', 'verification_status', 'timestamp')
    search_fields = ('scan_id', 'user__username', 'card__card_number', 'failure_reason', 'operator_id')
    ordering = ('-timestamp',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'timestamp'
    form = JSONFieldModelAdminForm

    fieldsets = (
        ('Relations principales', {
            'fields': ('user', 'card', 'trip')
        }),
        ('Informations de scan', {
            'fields': ('scan_id', 'scan_type', 'scan_data')
        }),
        ('Statut et vérification', {
            'fields': ('scan_status', 'verification_status', 'verification_timestamp', 'is_valid', 'failure_reason', 'error_details')
        }),
        ('Temporalité', {
            'fields': ('timestamp', 'expiry_time')
        }),
        ('Localisation', {
            'fields': ('station_id', 'location_data')
        }),
        ('Métadonnées', {
            'fields': ('device_info', 'operator_id', 'created_at', 'updated_at')
        }),
    )
