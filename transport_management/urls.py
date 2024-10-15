from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OCPViewSet, ScheduleViewSet, DriverViewSet, VehicleViewSet, DriverVehicleAssignmentViewSet

router = DefaultRouter()
router.register(r'ocps', OCPViewSet)
router.register(r'schedules', ScheduleViewSet)
router.register(r'vehicles', VehicleViewSet)
router.register(r'drivers', DriverViewSet)
router.register(r'assignments', DriverVehicleAssignmentViewSet)


urlpatterns = [
    path('', include(router.urls)),
]