# transport_api/serializers.py

from rest_framework import serializers
from .models import (
    OperationalRule, RuleExecution, RuleParameter, RuleSet, RuleSetMembership,
    Destination, Route, Stop, RouteStop, Schedule, ScheduleException,
    ResourceAvailability, Driver
)

class OperationalRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalRule
        fields = '__all__'

class RuleExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleExecution
        fields = '__all__'

class RuleParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleParameter
        fields = '__all__'

class RuleSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleSet
        fields = '__all__'

class DestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = '__all__'

class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = '__all__'

class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = '__all__'

class RouteStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteStop
        fields = '__all__'

class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = '__all__'

class ScheduleExceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleException
        fields = '__all__'

class ResourceAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceAvailability
        fields = '__all__'

class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = '__all__'
