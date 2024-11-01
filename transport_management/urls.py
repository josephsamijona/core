# transport_api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OperationalRulecViewSet, RuleExecutioncViewSet, RuleParametercViewSet,
    RuleSetViewSet, DestinationcViewSet, RoutecViewSet, StopcViewSet,
    SchedulecViewSet, ResourcecAvailabilityViewSet, DrivercViewSet, 
    DestinationgestionViewSet, RouteintiViewSet, StopViewSet, RouteStopViewSet,ResourceAvailabilityViewSet,SchedulesetupViewSet, ScheduleExceptionsetupViewSet,DriverViewSet
)

router = DefaultRouter()

# Enregistrement avec basenames uniques pour éviter les conflits
router.register(r'operational-rules', OperationalRulecViewSet, basename='operational-rule')
router.register(r'rule-executions', RuleExecutioncViewSet, basename='rule-execution')
router.register(r'rule-parameters', RuleParametercViewSet, basename='rule-parameter')
router.register(r'rule-sets', RuleSetViewSet, basename='rule-set')
router.register(r'destinations', DestinationcViewSet, basename='destination')
router.register(r'destinations-manage', DestinationgestionViewSet, basename='destination-manage')  # Renommé
router.register(r'routes', RoutecViewSet, basename='route')
router.register(r'stops', StopcViewSet, basename='stop')
router.register(r'stops-detail', StopViewSet, basename='stop-detail')  # Renommé
router.register(r'schedules', SchedulecViewSet, basename='schedules')
router.register(r'resource-availabilities', ResourcecAvailabilityViewSet, basename='resource-availability')
router.register(r'drivers', DrivercViewSet, basename='driver')
router.register(r'route-inti', RouteintiViewSet, basename='route-inti')  # Ajout du basename
router.register(r'route-stops', RouteStopViewSet, basename='route-stop')
router.register(r'Schedulesetup', SchedulesetupViewSet, basename='Schedulesetup')
router.register(r'ScheduleExceptionsetup', ScheduleExceptionsetupViewSet, basename='ScheduleExceptionsetup')
router.register(r'driversetup', DriverViewSet, basename='driversetup')
router.register(r'resource-availabilitiesetup', ResourceAvailabilityViewSet, basename='resource-availabilitiesetup')

urlpatterns = [
    path('', include(router.urls)),
]