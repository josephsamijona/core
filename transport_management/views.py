from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import time as datetime_time
from .models import Schedule, OperationalControlPlan, Route, Driver, DriverVehicleAssignment
from inventory_management.models import Vehicle
from .serializers import ScheduleSerializer
from datetime import timedelta, time, datetime, date
from rest_framework import exceptions
from .serializers import OCPSerializer, OCPListSerializer, OCPActivationSerializer
from .serializers import ScheduleSerializer, VehicleSerializer, DriverVehicleAssignmentSerializer, DriverSerializer
from datetime import timedelta, time, datetime, date

class OCPViewSet(viewsets.ModelViewSet):
    queryset = OperationalControlPlan.objects.all()
    serializer_class = OCPSerializer

    def get_serializer_class(self):
        if self.action == 'list':
            return OCPListSerializer
        return OCPSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save()
        self.check_and_renew_ocps()

    def perform_destroy(self, instance):
        if instance.is_active:
            raise exceptions.ValidationError({"detail": "Cannot delete an active OCP."})
        instance.delete()

    @action(detail=True, methods=['patch'])
    def activate(self, request, pk=None):
        ocp = self.get_object()
        serializer = OCPActivationSerializer(data=request.data)
        
        if serializer.is_valid():
            is_active = serializer.validated_data['is_active']
            if is_active:
                # Désactiver tous les autres OCPs
                OperationalControlPlan.objects.exclude(pk=ocp.pk).update(is_active=False)
            ocp.is_active = is_active
            ocp.save()
            return Response({'status': 'OCP updated'})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def active(self, request):
        active_ocp = OperationalControlPlan.objects.filter(is_active=True).first()
        if active_ocp:
            serializer = self.get_serializer(active_ocp)
            return Response(serializer.data)
        else:
            return Response({'detail': 'No active OCP found.'}, status=status.HTTP_404_NOT_FOUND)

    def check_and_renew_ocps(self):
        now = timezone.now()
        active_ocp = OperationalControlPlan.objects.filter(is_active=True).first()
        
        if active_ocp and active_ocp.end_date <= now:
            future_ocp = OperationalControlPlan.objects.filter(start_date__gt=now).order_by('start_date').first()
            
            if not future_ocp:
                new_ocp_data = {
                    field.name: getattr(active_ocp, field.name)
                    for field in active_ocp._meta.fields
                    if field.name not in ['id', 'name', 'start_date', 'end_date', 'created_at', 'updated_at', 'is_active', 'is_renewed', 'created_by']
                }
                new_ocp = OperationalControlPlan.objects.create(
                    name=f"{active_ocp.name} (Renewed)",
                    start_date=now,
                    end_date=now + timedelta(days=30),
                    created_by=active_ocp.created_by,
                    is_active=True,
                    is_renewed=True,
                    **new_ocp_data
                )
                active_ocp.is_active = False
                active_ocp.save()
            else:
                future_ocp.is_active = True
                future_ocp.save()
                active_ocp.is_active = False
                active_ocp.save()

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        self.check_and_renew_ocps()
        return response
    
class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer

    @action(detail=False, methods=['post'])
    def generate_schedules(self, request):
        ocp_id = request.data.get('ocp_id')
        try:
            ocp = OperationalControlPlan.objects.get(id=ocp_id)
        except OperationalControlPlan.DoesNotExist:
            return Response({"error": "OCP not found"}, status=status.HTTP_404_NOT_FOUND)

        routes = Route.objects.filter(ocp=ocp)
        
        schedules_created = 0
        for route in routes:
            for day in Schedule.DAY_CHOICES:
                day_name = day[0]
                if day_name in ocp.active_days:
                    start_datetime = timezone.datetime.combine(timezone.now().date(), datetime_time(hour=6, minute=0))
                    end_datetime = timezone.datetime.combine(timezone.now().date(), datetime_time(hour=22, minute=0))
                    current_datetime = start_datetime
                    
                    while current_datetime < end_datetime:
                        end_trip_datetime = current_datetime + timedelta(minutes=ocp.buffer_time_between_trips)
                        Schedule.objects.create(
                            ocp=ocp,
                            route=route,
                            start_time=current_datetime,
                            end_time=end_trip_datetime,
                            frequency=ocp.frequency,
                            day_of_week=day_name
                        )
                        schedules_created += 1
                        current_datetime += timedelta(minutes=ocp.frequency)

        return Response({"message": f"{schedules_created} schedules generated successfully"}, status=status.HTTP_201_CREATED)
        
    @action(detail=False, methods=['post'])
    def assign_resources(self, request):
        date = request.data.get('date', timezone.now().date())
        schedules = Schedule.objects.filter(start_time__date=date)
        
        for schedule in schedules:
            available_drivers = Driver.objects.filter(
                employment_status='active',
                availability_status='available'
            ).exclude(
                drivervehicleassignment__assigned_from__date=date
            )
            
            available_vehicles = Vehicle.objects.filter(
                status='operational'
            ).exclude(
                drivervehicleassignment__assigned_from__date=date
            )
            
            if available_drivers.exists() and available_vehicles.exists():
                driver = available_drivers.first()
                vehicle = available_vehicles.first()
                
                DriverVehicleAssignment.objects.create(
                    driver=driver,
                    vehicle=vehicle,
                    assigned_from=schedule.start_time,
                    assigned_until=schedule.end_time
                )
        
        return Response({"message": "Resources assigned successfully"}, status=status.HTTP_200_OK)

class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer

    @action(detail=True, methods=['post'])
    def assign_driver(self, request, pk=None):
        vehicle = self.get_object()
        driver_id = request.data.get('driver_id')
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')

        try:
            driver = Driver.objects.get(id=driver_id)
        except Driver.DoesNotExist:
            return Response({"error": "Driver not found"}, status=status.HTTP_404_NOT_FOUND)

        assignment = DriverVehicleAssignment.objects.create(
            driver=driver,
            vehicle=vehicle,
            assigned_from=start_time,
            assigned_until=end_time
        )

        return Response(DriverVehicleAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer

    @action(detail=True, methods=['get'])
    def available_vehicles(self, request, pk=None):
        driver = self.get_object()
        date = request.query_params.get('date', timezone.now().date())

        available_vehicles = Vehicle.objects.exclude(
            drivervehicleassignment__driver=driver,
            drivervehicleassignment__assigned_from__date=date
        )

        return Response(VehicleSerializer(available_vehicles, many=True).data)

class DriverVehicleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = DriverVehicleAssignment.objects.all()
    serializer_class = DriverVehicleAssignmentSerializer

    
    @action(detail=False, methods=['post'])
    def auto_assign(self, request):
        date = request.data.get('date', timezone.now().date())
        schedules = Schedule.objects.filter(start_time__date=date)
        
        for schedule in schedules:
            available_drivers = Driver.objects.filter(
                employment_status='active',
                availability_status='available'
            ).exclude(
                drivervehicleassignment__assigned_from__date=date
            )
            
            available_vehicles = Vehicle.objects.filter(
                status='operational'
            ).exclude(
                drivervehicleassignment__assigned_from__date=date
            )
            
            if available_drivers.exists() and available_vehicles.exists():
                driver = available_drivers.first()
                vehicle = available_vehicles.first()
                
                DriverVehicleAssignment.objects.create(
                    driver=driver,
                    vehicle=vehicle,
                    assigned_from=schedule.start_time,
                    assigned_until=schedule.end_time
                )
        
        return Response({"message": "Auto-assignment completed"}, status=status.HTTP_200_OK)