# inventory_management/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, SupplierViewSet, InventoryItemViewSet, ItemViewSet, VehicleViewSet, VehicleMaintenanceViewSet ,InventoryUtilsView

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'inventory-items', InventoryItemViewSet)
router.register(r'items', ItemViewSet, basename='item')
router.register(r'vehicles', VehicleViewSet)
router.register(r'vehicle-maintenances', VehicleMaintenanceViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('inventory-utils/', InventoryUtilsView.as_view(), name='inventory-utils'),
]