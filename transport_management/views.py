# transport_api/views.py
from rest_framework.views import APIView
from django.db.models import Q, Count, Sum
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    OperationalRule, RuleExecution, RuleParameter, RuleSet, Destination,
    Route, Stop, Schedule, ResourceAvailability, Driver, RouteStop, ScheduleException,Trip, BusPosition, EventLog, DisplaySchedule
)
from transport_management.services.tracking.position_tracking import PositionTrackingService
from transport_management.services.event.event_manager import TripEventManager
from inventory_management.serializers import VehicleSerializer
from inventory_management.models import Vehicle
from .serializers import (
    OperationalRuleSerializercrud, RuleExecutionSerializercrud, RuleParameterSerializercrud,
    RuleSetSerializercrud, DestinationSerializercrud, RouteSerializercrud, StopSerializercrud,
    ScheduleSerializercrud, ResourceAvailabilitySerializercrud, DriverSerializercrud, DestinationSerializer,
    RouteitinineraireSerializer, DestinationitinineraireSerializer, StoparretSerializer, RouteStoparretSerializer,
    ScheduleautomatSerializer, ScheduleExceptionSerializercrud, DriverSerializer, ResourceAvailabilitySerializer,    TripSerializer, 
    TripDetailSerializer, 
    PositionUpdateSerializer,
    TripEventSerializer, DisplayScheduleSerializer
)
import logging

logger = logging.getLogger(__name__)

SCHEDULE_LOCK_TIMEOUT = 300  # 5 minutes
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
        today = timezone.now().date()
        
        # Filtres de base
        queryset = queryset.filter(
            start_date__lte=today,
            end_date__gte=today,
            day_of_week=today.strftime('%A').lower(),
            is_active=True
        )

        # Filtres supplémentaires
        status_param = self.request.query_params.get('status')
        route = self.request.query_params.get('route')
        season = self.request.query_params.get('season')
        is_current = self.request.query_params.get('is_current')
        destination = self.request.query_params.get('destination')  # Nouveau filtre

        if status_param:
            queryset = queryset.filter(status=status_param)
        if route:
            queryset = queryset.filter(route_id=route)
        if season:
            queryset = queryset.filter(season=season)
        if is_current is not None:
            queryset = queryset.filter(is_current_version=is_current.lower() == 'true')
        if destination:
            queryset = queryset.filter(destination_id=destination)  # Application du filtre

        return queryset.select_related('route', 'destination', 'approved_by', 'created_by')  # Ajout de 'destination'

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        with transaction.atomic():
            lock_id = f"schedule_update_{serializer.instance.id}"
            if not cache.add(lock_id, True, SCHEDULE_LOCK_TIMEOUT):
                raise ValidationError("L'horaire est en cours de modification.")
            try:
                serializer.save()
            finally:
                cache.delete(lock_id)

    def perform_destroy(self, instance):
        lock_id = f"schedule_delete_{instance.id}"
        if not cache.add(lock_id, True, SCHEDULE_LOCK_TIMEOUT):
            raise ValidationError("L'horaire est en cours de suppression.")
        try:
            instance.is_active = False
            instance.status = 'archived'
            instance.save()
        finally:
            cache.delete(lock_id)

    @action(detail=True, methods=['post'])
    def validate_schedule(self, request, pk=None):
        lock_id = f"schedule_validate_{pk}"
        if not cache.add(lock_id, True, SCHEDULE_LOCK_TIMEOUT):
            return Response(
                {'detail': 'Validation en cours.'},
                status=status.HTTP_409_CONFLICT
            )

        try:
            with transaction.atomic():
                schedule = self.get_object()
                
                if schedule.is_approved:
                    return Response(
                        {'detail': 'Horaire déjà approuvé.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Validation de l'horaire
                schedule.is_approved = True
                schedule.approval_date = timezone.now()
                schedule.approved_by = request.user
                schedule.status = 'validated'

                # Activation automatique si la date est aujourd'hui ou future
                if schedule.start_date <= timezone.now().date():
                    schedule.status = 'active'
                    schedule.is_current_version = True
                    generate_daily_schedules.delay()

                schedule.save()
                logger.info(f"Horaire {pk} validé par {request.user}")

                return Response({
                    'detail': 'Horaire validé avec succès.',
                    'status': schedule.status
                })

        except Exception as e:
            logger.error(f"Erreur lors de la validation: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        finally:
            cache.delete(lock_id)

    @action(detail=True, methods=['post'])
    def activate_schedule(self, request, pk=None):
        lock_id = f"schedule_activate_{pk}"
        if not cache.add(lock_id, True, SCHEDULE_LOCK_TIMEOUT):
            return Response(
                {'detail': 'Activation en cours.'},
                status=status.HTTP_409_CONFLICT
            )

        try:
            with transaction.atomic():
                schedule = self.get_object()
                if not schedule.is_approved:
                    return Response(
                        {'detail': 'Validation requise avant activation.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                schedule.status = 'active'
                schedule.is_current_version = True
                schedule.save()
                
                generate_daily_schedules.delay()
                logger.info(f"Horaire {pk} activé par {request.user}")
                
                return Response({'detail': 'Horaire activé avec succès.'})

        except Exception as e:
            logger.error(f"Erreur lors de l'activation: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        finally:
            cache.delete(lock_id)

    @action(detail=False, methods=['get'])
    def active_schedules(self, request):
        active_schedules = self.get_queryset().filter(
            status='active',
            is_current_version=True
        )
        serializer = self.get_serializer(active_schedules, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def timepoints(self, request, pk=None):
        schedule = self.get_object()
        date_str = request.query_params.get('date')
        
        try:
            date = (
                timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
                if date_str else timezone.now().date()
            )
            schedule.generate_timepoints_for_date(date)
            
            return Response({
                'schedule_id': schedule.id,
                'date': date,
                'timepoints': schedule.timepoints
            })
            
        except ValueError:
            return Response(
                {'error': 'Format de date invalide (YYYY-MM-DD)'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        return Response({
            'total': Schedule.objects.count(),
            'active': Schedule.objects.filter(status='active').count(),
            'pending': Schedule.objects.filter(status='pending').count(),
            'last_update': timezone.now()
        })
    
    
    

# ViewSet for managing ScheduleException with additional functionalities
class ScheduleExceptionsetupViewSet(viewsets.ModelViewSet):
    queryset = ScheduleException.objects.all()
    serializer_class = ScheduleExceptionSerializercrud
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



# transport_management/api/v1/views.py



class TripViewSet(viewsets.ModelViewSet):
    """
    API endpoint pour la gestion des trips
    """
    serializer_class = TripSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Trip.objects.all()
        return Trip.objects.filter(driver=user)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TripDetailSerializer
        return TripSerializer

    @action(detail=True, methods=['post'])
    def start_trip(self, request, pk=None):
        """Démarre un trip"""
        trip = self.get_object()
        # Logique de démarrage du trip
        return Response({'status': 'trip started'})

    @action(detail=True, methods=['post'])
    def end_trip(self, request, pk=None):
        """Termine un trip"""
        trip = self.get_object()
        # Logique de fin du trip
        return Response({'status': 'trip ended'})

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Obtient le statut détaillé d'un trip"""
        trip = self.get_object()
        serializer = TripDetailSerializer(trip)
        return Response(serializer.data)

class TripTrackingViewSet(viewsets.ViewSet):
    """
    API endpoint pour le tracking GPS des trips
    """
    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tracking_service = PositionTrackingService()

    @action(detail=False, methods=['post'])
    def update_position(self, request):
        """
        Met à jour la position du bus
        """
        serializer = PositionUpdateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                position = self.tracking_service.process_gps_data(serializer.validated_data)
                return Response({
                    'status': 'success',
                    'position_id': position.id
                })
            except Exception as e:
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def latest_position(self, request, pk=None):
        """
        Obtient la dernière position d'un trip
        """
        try:
            position = BusPosition.objects.filter(
                trip_id=pk
            ).order_by('-timestamp').first()

            if position:
                return Response({
                    'latitude': position.latitude,
                    'longitude': position.longitude,
                    'speed': position.speed,
                    'timestamp': position.timestamp
                })
            return Response({'message': 'No position found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class TripEventViewSet(viewsets.ModelViewSet):
    """
    API endpoint pour la gestion des événements de trip
    """
    serializer_class = TripEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EventLog.objects.all()

    @action(detail=False, methods=['post'])
    def report_incident(self, request):
        """
        Signale un incident sur un trip
        """
        try:
            # Logique de signalement d'incident
            return Response({'status': 'incident reported'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class DriverTripViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint pour les chauffeurs
    """
    serializer_class = TripDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Trip.objects.filter(driver=self.request.user)

    @action(detail=False, methods=['get'])
    def current_trip(self, request):
        """
        Obtient le trip actuel du chauffeur
        """
        trip = Trip.objects.filter(
            driver=request.user,
            status='in_progress'
        ).first()

        if trip:
            serializer = self.get_serializer(trip)
            return Response(serializer.data)
        return Response({'message': 'No active trip'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def report_issue(self, request, pk=None):
        """
        Permet au chauffeur de signaler un problème
        """
        trip = self.get_object()
        # Logique de signalement
        return Response({'status': 'issue reported'})
    
    
    
    
class TodayDisplayScheduleAPIView(APIView):
    """
    Vue pour récupérer les DisplaySchedules du jour actuel, uniquement pour les trips non terminés.
    """
    def get(self, request):
        today = timezone.localdate()
        start_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        end_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))

        # Filtrer les DisplaySchedules du jour dont le trip n'est pas terminé
        display_schedules = DisplaySchedule.objects.filter(
            scheduled_departure__range=(start_of_day, end_of_day),
            trip__status__in=['scheduled', 'boarding_soon', 'boarding', 'in_transit', 'arriving_soon']
        ).order_by('scheduled_departure')

        serializer = DisplayScheduleSerializer(display_schedules, many=True)
        return Response(serializer.data)