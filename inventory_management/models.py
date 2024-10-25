from django.db import models
from django.utils import timezone
from django.db.models import F

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    services_provided = models.TextField(blank=True)

    def __str__(self):
        return self.name

class InventoryItem(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True)
    reorder_level = models.IntegerField(default=10)
    last_restocked = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - Quantity: {self.quantity}"

    def is_low_stock(self):
        return self.quantity <= self.reorder_level
    

class Item(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Vehicle(models.Model):
    VEHICLE_TYPES = [
        ('bus', 'Bus'),
        ('minibus', 'Minibus'),
        ('van', 'Van'),
    ]

    FUEL_TYPES = [
        ('diesel', 'Diesel'),
        ('gasoline', 'Gasoline'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('maintenance', 'In Maintenance'),
        ('out_of_service', 'Out of Service'),
    ]

    vehicle_number = models.CharField(max_length=20, unique=True)
    type = models.CharField(max_length=20, choices=VEHICLE_TYPES)
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.IntegerField(default=2000)
    capacity = models.IntegerField(default=1)
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPES)
    license_plate = models.CharField(max_length=20, unique=True)
    mileage = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.vehicle_number} ({self.license_plate})"

class VehicleMaintenance(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='maintenances')
    maintenance_type = models.CharField(max_length=100)
    description = models.TextField()
    date_performed = models.DateField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    performed_by = models.CharField(max_length=100)
    next_maintenance_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Maintenance for {self.vehicle.vehicle_number} on {self.date_performed}"

    class Meta:
        ordering = ['-date_performed']
        