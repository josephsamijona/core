from rest_framework import serializers
from .models import OperationalControlPlan, Schedule, Driver, DriverSchedule, DriverVehicleAssignment
from inventory_management.models import Vehicle

class OCPSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalControlPlan
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'is_renewed']

    def validate(self, data):
        if data.get('end_date') and data.get('start_date') and data['end_date'] <= data['start_date']:
            raise serializers.ValidationError("La date de fin doit être postérieure à la date de début.")
        return data

class OCPListSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalControlPlan
        fields = ['id', 'name', 'start_date', 'end_date', 'is_active', 'is_renewed']

class OCPActivationSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()
    
class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = '__all__'

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time.")
        if data['frequency'] <= 0:
            raise serializers.ValidationError("Frequency must be a positive integer.")
        return data
    
class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = '__all__'

class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = '__all__'

class DriverVehicleAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverVehicleAssignment
        fields = '__all__'