# transport_api/views.py
from django.db.models import Q, Count, Sum
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    OperationalRule, RuleExecution, RuleParameter, RuleSet, Destination,
    Route, Stop, Schedule, ResourceAvailability, Driver, RouteStop, ScheduleException
)
from inventory_management.serializers import VehicleSerializer
from inventory_management.models import Vehicle
from .serializers import (
    OperationalRuleSerializercrud, RuleExecutionSerializercrud, RuleParameterSerializercrud,
    RuleSetSerializercrud, DestinationSerializercrud, RouteSerializercrud, StopSerializercrud,
    ScheduleSerializercrud, ResourceAvailabilitySerializercrud, DriverSerializercrud, DestinationSerializer,
    RouteitinineraireSerializer, DestinationitinineraireSerializer, StoparretSerializer, RouteStoparretSerializer,
    ScheduleautomatSerializer, ScheduleautomaExceptionSerializer, DriverSerializer, ResourceAvailabilitySerializer
)

# ViewSet for OperationalRule model
class OperationalRulecViewSet(viewsets.ModelViewSet):
    queryset = OperationalRule.objects.all()
    serializer_class = OperationalRuleSerializercrud
    permission_classes = [IsAuthenticated]

# ViewSet for RuleExecution model
class RuleExecutioncViewSet(viewsets.ModelViewSet):
    queryset = RuleExecution.objects.all()
    serializer_class = RuleExecutionSerializercrud
    permission_classes = [IsAuthenticated]

# ViewSet for RuleParameter model
class RuleParametercViewSet(viewsets.ModelViewSet):
    queryset = RuleParameter.objects.all()
    serializer_class = RuleParameterSerializercrud    
    permission_classes = [IsAuthenticated]

# ViewSet for RuleSet model
class RuleSetViewSet(viewsets.ModelViewSet):
    queryset = RuleSet.objects.all()
    serializer_class = RuleSetSerializercrud    
    permission_classes = [IsAuthenticated]

# ViewSet for Destination model
class DestinationcViewSet(viewsets.ModelViewSet):
    queryset = Destination.objects.all()
    serializer_class = DestinationSerializercrud
    permission_classes = [IsAuthenticated]

# ViewSet for Route model
class RoutecViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializercrud
    permission_classes = [IsAuthenticated]

# ViewSet for Stop model
class StopcViewSet(viewsets.ModelViewSet):
    queryset = Stop.objects.all()
    serializer_class = StopSerializercrud
    permission_classes = [IsAuthenticated]

# ViewSet for Schedule model
class SchedulecViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializercrud
    permission_classes = [IsAuthenticated]    

# ViewSet for ResourceAvailability model
class ResourcecAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = ResourceAvailability.objects.all()
    serializer_class = ResourceAvailabilitySerializercrud
    permission_classes = [IsAuthenticated]

# ViewSet for Driver model
class DrivercViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializercrud
    permission_classes = [IsAuthenticated]

# ViewSet for managing Destination with additional functionalities
class DestinationgestionViewSet(viewsets.ModelViewSet):
    queryset = Destination.objects.all()
    serializer_class = DestinationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['zone_code', 'circuit', 'category', 'destination_type']
    search_fields = ['name', 'locality', 'description']
    ordering_fields = ['name', 'estimated_daily_traffic']

    @action(detail=False, methods=['get'])
    def traffic_statistics(self, request):
        """
        Endpoint to calculate and display traffic statistics.
        """
        total_traffic = Destination.objects.aggregate(total=Sum('estimated_daily_traffic'))
        return Response({'total_estimated_daily_traffic': total_traffic['total']})

    @action(detail=False, methods=['get'])
    def map_data(self, request):
        """
        Endpoint to get data necessary for mapping.
        """
        destinations = self.get_queryset()
        serializer = self.get_serializer(destinations, many=True)
        return Response(serializer.data)

# ViewSet for managing Route with additional functionalities
class RouteintiViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteitinineraireSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['route_code', 'route_category', 'status']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'total_distance']

    @action(detail=True, methods=['get'])
    def map_data(self, request, pk=None):
        """
        Endpoint to get data necessary for mapping a route.
        """
        route = self.get_object()
        serializer = self.get_serializer(route)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def calculate_metrics(self, request, pk=None):
        """
        Action to recalculate estimated distances and durations.
        """
        route = self.get_object()
        route.calculate_metrics()
        route.save()
        serializer = self.get_serializer(route)
        return Response(serializer.data)

# ViewSet for managing Stop with additional functionalities
class StopViewSet(viewsets.ModelViewSet):
    queryset = Stop.objects.all()
    serializer_class = StoparretSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['zone_code', 'service_zone', 'stop_type', 'status']
    search_fields = ['name', 'description', 'address']
    ordering_fields = ['name', 'average_waiting_time']

    @action(detail=True, methods=['get'])
    def average_wait_time(self, request, pk=None):
        """
        Endpoint to get the average waiting time at a stop.
        """
        stop = self.get_object()
        return Response({'average_waiting_time': stop.average_waiting_time})

# ViewSet for managing RouteStop with additional functionalities
class RouteStopViewSet(viewsets.ModelViewSet):
    queryset = RouteStop.objects.all()
    serializer_class = RouteStoparretSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['route', 'stop']
    ordering_fields = ['order', 'stop_sequence']

# ViewSet for managing Schedule with additional functionalities
class SchedulesetupViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleautomatSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter to show only today's schedules
        today = timezone.now().date()
        return queryset.filter(
            start_date__lte=today,
            end_date__gte=today,
            day_of_week=today.strftime('%A').lower(),
            is_active=True
        )

    @action(detail=True, methods=['post'])
    def validate_schedule(self, request, pk=None):
        """
        Action to validate a schedule.
        """
        schedule = self.get_object()
        if schedule.is_approved:
            return Response({'detail': 'This schedule is already approved.'}, status=status.HTTP_400_BAD_REQUEST)
        schedule.is_approved = True
        schedule.approval_date = timezone.now()
        schedule.approved_by = request.user
        schedule.save()
        return Response({'detail': 'Schedule successfully validated.'}, status=status.HTTP_200_OK)

# ViewSet for managing ScheduleException with additional functionalities
class ScheduleExceptionsetupViewSet(viewsets.ModelViewSet):
    queryset = ScheduleException.objects.all()
    serializer_class = ScheduleautomaExceptionSerializer
    permission_classes = [IsAuthenticated]

# ViewSet for managing Driver with additional functionalities
class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['employment_status', 'availability_status', 'license_type']
    search_fields = ['first_name', 'last_name', 'employee_id', 'email']
    ordering_fields = ['last_name', 'rating', 'total_trips', 'total_hours']

    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """
        Endpoint to get driver performance.
        """
        driver = self.get_object()
        data = {
            'rating': driver.rating,
            'total_trips': driver.total_trips,
            'total_hours': driver.total_hours,
            'performance_metrics': driver.performance_metrics
        }
        return Response(data)

    @action(detail=True, methods=['get'])
    def working_hours(self, request, pk=None):
        """
        Endpoint to get driver working hours.
        """
        driver = self.get_object()
        total_hours = driver.total_hours
        maximum_hours = driver.maximum_hours_per_week
        data = {
            'total_hours_worked': total_hours,
            'maximum_hours_per_week': maximum_hours,
            'hours_remaining': maximum_hours - total_hours
        }
        return Response(data)

    @action(detail=True, methods=['post'])
    def update_performance(self, request, pk=None):
        """
        Action to update driver performance.
        """
        driver = self.get_object()
        driver.update_performance_metrics()
        driver.save()
        return Response({'detail': 'Performance updated successfully.'}, status=status.HTTP_200_OK)

# ViewSet for managing ResourceAvailability with additional functionalities
class ResourceAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = ResourceAvailability.objects.all()
    serializer_class = ResourceAvailabilitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['resource_type', 'status', 'date', 'driver', 'vehicle']
    search_fields = []
    ordering_fields = ['date', 'start_time', 'priority_level']

    @action(detail=False, methods=['get'])
    def available_drivers(self, request):
        """
        Endpoint to get available drivers for a given date and time range.
        """
        date = request.query_params.get('date')
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        if not date or not start_time or not end_time:
            return Response({'detail': 'Please provide date, start time, and end time.'},
                            status=status.HTTP_400_BAD_REQUEST)
        available_drivers = ResourceAvailability.objects.filter(
            resource_type='driver',
            date=date,
            start_time__lte=start_time,
            end_time__gte=end_time,
            is_available=True
        ).values('driver')
        drivers = Driver.objects.filter(id__in=available_drivers)
        serializer = DriverSerializer(drivers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def available_vehicles(self, request):
        """
        Endpoint to get available vehicles for a given date and time range.
        """
        date = request.query_params.get('date')
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        if not date or not start_time or not end_time:
            return Response({'detail': 'Please provide date, start time, and end time.'},
                            status=status.HTTP_400_BAD_REQUEST)
        available_vehicles = ResourceAvailability.objects.filter(
            resource_type='vehicle',
            date=date,
            start_time__lte=start_time,
            end_time__gte=end_time,
            is_available=True
        ).values('vehicle')
        vehicles = Vehicle.objects.filter(id__in=available_vehicles)
        serializer = VehicleSerializer(vehicles, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def plan_resources(self, request):
        """
        Action to plan resources (driver and vehicle) for a given time range.
        """
        date = request.data.get('date')
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        if not date or not start_time or not end_time:
            return Response({'detail': 'Please provide date, start time, and end time.'},
                            status=status.HTTP_400_BAD_REQUEST)
        available_drivers = ResourceAvailability.objects.filter(
            resource_type='driver',
            date=date,
            start_time__lte=start_time,
            end_time__gte=end_time,
            is_available=True
        ).order_by('priority_level')
        available_vehicles = ResourceAvailability.objects.filter(
            resource_type='vehicle',
            date=date,
            start_time__lte=start_time,
            end_time__gte=end_time,
            is_available=True
        ).order_by('priority_level')
        if not available_drivers.exists() or not available_vehicles.exists():
            return Response({'detail': 'No available driver or vehicle for this time range.'},
                            status=status.HTTP_400_BAD_REQUEST)
        driver_availability = available_drivers.first()
        vehicle_availability = available_vehicles.first()
        driver_availability.status = 'reserved'
        driver_availability.save()
        vehicle_availability.status = 'reserved'
        vehicle_availability.save()
        data = {
            'driver': DriverSerializer(driver_availability.driver).data,
            'vehicle': VehicleSerializer(vehicle_availability.vehicle).data
        }
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def detect_conflicts(self, request):
        """
        Endpoint to detect resource conflicts.
        """
        date = request.query_params.get('date')
        if not date:
            return Response({'detail': 'Please provide date.'},
                            status=status.HTTP_400_BAD_REQUEST)
        conflicts = ResourceAvailability.objects.filter(
            date=date,
            is_available=True
        ).values('driver', 'vehicle', 'start_time', 'end_time').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        return Response({'conflicts': list(conflicts)}, status=status.HTTP_200_OK)
