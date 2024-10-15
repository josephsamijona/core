from rest_framework import serializers
from .models import Category, Supplier, InventoryItem,Item, Vehicle,VehicleMaintenance

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']
        
class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'contact_person', 'phone_number', 'email', 'address', 'services_provided']
        
class InventoryItemSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = ['id', 'name', 'category', 'quantity', 'unit_price', 'supplier', 'reorder_level', 'last_restocked', 'is_low_stock']

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'name', 'description', 'category', 'quantity', 'price', 'created_at', 'updated_at']

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = '__all__'
        
class VehicleMaintenanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleMaintenance
        fields = '__all__'