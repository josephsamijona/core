# inventory_management/views.py

from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.db.models import F
from django.utils import timezone
from .models import Category,Supplier, InventoryItem,Item, Vehicle, VehicleMaintenance
from .serializers import CategorySerializer, SupplierSerializer, InventoryItemSerializer, ItemSerializer, VehicleSerializer, VehicleMaintenanceSerializer
from .utils import (
    calculate_total_inventory_value,
    generate_inventory_report,
    generate_low_stock_alert,
    calculate_vehicle_maintenance_costs
)



class CategoryViewSet(viewsets.ViewSet):
    def create(self, request):
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        serializer = CategorySerializer(category, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def list(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        serializer = CategorySerializer(category)
        return Response(serializer.data)
    
    
class SupplierViewSet(viewsets.ViewSet):
    def create(self, request):
        serializer = SupplierSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        try:
            supplier = Supplier.objects.get(pk=pk)
        except Supplier.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        serializer = SupplierSerializer(supplier, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        try:
            supplier = Supplier.objects.get(pk=pk)
        except Supplier.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        supplier.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def list(self, request):
        suppliers = Supplier.objects.all()
        serializer = SupplierSerializer(suppliers, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        try:
            supplier = Supplier.objects.get(pk=pk)
        except Supplier.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        serializer = SupplierSerializer(supplier)
        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        try:
            supplier = Supplier.objects.get(pk=pk)
        except Supplier.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        serializer = SupplierSerializer(supplier, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    


class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer

    @action(detail=True, methods=['post'])
    def restock(self, request, pk=None):
        item = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        if quantity > 0:
            item.quantity += quantity
            item.save()
            return Response({'status': 'restocked'})
        else:
            return Response({'status': 'invalid quantity'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        low_stock_items = InventoryItem.objects.filter(quantity__lte=F('reorder_level'))
        serializer = self.get_serializer(low_stock_items, many=True)
        return Response(serializer.data)
    
class ItemViewSet(viewsets.ViewSet):

    def create(self, request):
        data = request.data
        try:
            category = Category.objects.get(id=data.get('category'))
        except Category.DoesNotExist:
            return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        try:
            item = Item.objects.get(pk=pk)
        except Item.DoesNotExist:
            return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

        # Vérifie que la catégorie existe si elle est incluse dans la mise à jour
        if 'category' in request.data:
            try:
                Category.objects.get(id=request.data['category'])
            except Category.DoesNotExist:
                return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ItemSerializer(item, data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            # Ajoute cette ligne pour voir toutes les erreurs de validation
            print(serializer.errors)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



    def partial_update(self, request, pk=None):
        try:
            item = Item.objects.get(pk=pk)
        except Item.DoesNotExist:
            return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

        # Vérifie que la catégorie existe si elle est incluse dans la mise à jour partielle
        if 'category' in request.data:
            try:
                Category.objects.get(id=request.data['category'])
            except Category.DoesNotExist:
                return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ItemSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def destroy(self, request, pk=None):
        try:
            item = Item.objects.get(pk=pk)
        except Item.DoesNotExist:
            return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def list(self, request):
        items = Item.objects.all()
        serializer = ItemSerializer(items, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        try:
            item = Item.objects.get(pk=pk)
        except Item.DoesNotExist:
            return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ItemSerializer(item)
        return Response(serializer.data)
    
class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer

    @action(detail=True, methods=['patch'])
    def update_mileage(self, request, pk=None):
        vehicle = self.get_object()
        new_mileage = request.data.get('mileage')
        if new_mileage is not None and new_mileage > vehicle.mileage:
            vehicle.mileage = new_mileage
            vehicle.save()
            return Response({'status': 'mileage updated'})
        return Response({'status': 'invalid mileage'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def change_status(self, request, pk=None):
        vehicle = self.get_object()
        new_status = request.data.get('status')
        if new_status in dict(Vehicle.STATUS_CHOICES):
            vehicle.status = new_status
            vehicle.save()
            return Response({'status': 'vehicle status updated'})
        return Response({'status': 'invalid status'}, status=status.HTTP_400_BAD_REQUEST)
    
class VehicleMaintenanceViewSet(viewsets.ModelViewSet):
    queryset = VehicleMaintenance.objects.all()
    serializer_class = VehicleMaintenanceSerializer

    @action(detail=False, methods=['get'])
    def upcoming_maintenances(self, request):
        upcoming = VehicleMaintenance.objects.filter(next_maintenance_date__gte=timezone.now().date()).order_by('next_maintenance_date')
        serializer = self.get_serializer(upcoming, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_for_vehicle(self, request):
        vehicle_id = request.query_params.get('vehicle_id')
        if vehicle_id:
            maintenances = VehicleMaintenance.objects.filter(vehicle_id=vehicle_id)
            serializer = self.get_serializer(maintenances, many=True)
            return Response(serializer.data)
        return Response({"error": "Vehicle ID is required"}, status=status.HTTP_400_BAD_REQUEST)
    
class InventoryUtilsView(APIView):
    def get(self, request, *args, **kwargs):
        action = request.query_params.get('action')
        
        if action == 'total_value':
            return Response({'total_value': calculate_total_inventory_value()})
        
        elif action == 'inventory_report':
            return Response(generate_inventory_report())
        
        elif action == 'low_stock_alert':
            return Response(generate_low_stock_alert())
        
        elif action == 'maintenance_costs':
            vehicle_id = request.query_params.get('vehicle_id')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            if not all([vehicle_id, start_date, end_date]):
                return Response({'error': 'Missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
            
            total_cost = calculate_vehicle_maintenance_costs(vehicle_id, start_date, end_date)
            return Response({'total_cost': total_cost})
        
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

