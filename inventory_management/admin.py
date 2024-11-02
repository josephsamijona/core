# inventory/admin.py

from django.contrib import admin
from .models import (
    Category,
    Supplier,
    InventoryItem,
    Item,
    Vehicle,
    VehicleMaintenance,
)

# Administration pour Category
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')
    list_filter = ('name',)
    ordering = ('name',)

# Administration pour Supplier
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone_number', 'email')
    search_fields = ('name', 'contact_person', 'email', 'phone_number')
    list_filter = ('name', 'services_provided')
    ordering = ('name',)

# Administration pour InventoryItem
@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'quantity',
        'unit_price',
        'supplier',
        'reorder_level',
        'last_restocked',
        'is_low_stock'
    )
    search_fields = ('name', 'category__name', 'supplier__name')
    list_filter = ('category', 'supplier', 'reorder_level')
    readonly_fields = ('last_restocked',)
    ordering = ('name',)

    def is_low_stock(self, obj):
        return obj.is_low_stock()
    is_low_stock.boolean = True
    is_low_stock.short_description = 'Stock Faible'

# Administration pour Item
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'price', 'created_at', 'updated_at')
    search_fields = ('name', 'category__name', 'description')
    list_filter = ('category', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('name',)

# Administration pour Vehicle
@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle_number',
        'type',
        'make',
        'model',
        'year',
        'capacity',
        'fuel_type',
        'license_plate',
        'mileage',
        'status'
    )
    search_fields = ('vehicle_number', 'license_plate', 'make', 'model')
    list_filter = ('type', 'fuel_type', 'status', 'year')
    ordering = ('vehicle_number',)

# Administration pour VehicleMaintenance
@admin.register(VehicleMaintenance)
class VehicleMaintenanceAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle',
        'maintenance_type',
        'date_performed',
        'cost',
        'performed_by',
        'next_maintenance_date'
    )
    search_fields = ('vehicle__vehicle_number', 'maintenance_type', 'performed_by')
    list_filter = ('maintenance_type', 'date_performed', 'next_maintenance_date')
    ordering = ('-date_performed',)
    readonly_fields = ('date_performed', 'next_maintenance_date')
