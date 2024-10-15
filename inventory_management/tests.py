# inventory_management/tests.py

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from .models import Category, Supplier, InventoryItem, Item,Vehicle, VehicleMaintenance
from datetime import date, timedelta

class CategoryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category_data = {'name': 'Test Category', 'description': 'Test Description'}
        self.response = self.client.post(
            reverse('category-list'),
            self.category_data,
            format="json")

    def test_create_category(self):
        """Test creating a new category"""
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Category.objects.get().name, 'Test Category')

    def test_get_all_categories(self):
        """Test getting all categories"""
        # Create another category
        Category.objects.create(name='Another Category', description='Another Description')
        
        response = self.client.get(reverse('category-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # We now have two categories

    def test_get_category_by_id(self):
        """Test getting a specific category by ID"""
        category = Category.objects.get()
        response = self.client.get(reverse('category-detail', kwargs={'pk': category.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Category')

    def test_update_category(self):
        """Test updating an existing category"""
        category = Category.objects.get()
        updated_data = {'name': 'Updated Category', 'description': 'Updated Description'}
        response = self.client.put(
            reverse('category-detail', kwargs={'pk': category.id}),
            updated_data,
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Category.objects.get().name, 'Updated Category')

    def test_partial_update_category(self):
        """Test partial update of a category"""
        category = Category.objects.get()
        partial_data = {'description': 'Partially Updated Description'}
        response = self.client.patch(
            reverse('category-detail', kwargs={'pk': category.id}),
            partial_data,
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Category.objects.get().description, 'Partially Updated Description')
        self.assertEqual(Category.objects.get().name, 'Test Category')  # Name should remain unchanged

    def test_delete_category(self):
        """Test deleting a category"""
        category = Category.objects.get()
        response = self.client.delete(reverse('category-detail', kwargs={'pk': category.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Category.objects.count(), 0)

    def test_create_invalid_category(self):
        """Test creating a new category with invalid data"""
        invalid_data = {'name': '', 'description': 'Invalid Category'}
        response = self.client.post(reverse('category-list'), invalid_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_non_existent_category(self):
        """Test updating a category that doesn't exist"""
        non_existent_id = 999
        updated_data = {'name': 'Updated Category', 'description': 'Updated Description'}
        response = self.client.put(
            reverse('category-detail', kwargs={'pk': non_existent_id}),
            updated_data,
            format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_non_existent_category(self):
        """Test deleting a category that doesn't exist"""
        non_existent_id = 999
        response = self.client.delete(reverse('category-detail', kwargs={'pk': non_existent_id}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        

class SupplierTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.supplier_data = {
            'name': 'Test Supplier',
            'contact_person': 'John Doe',
            'phone_number': '1234567890',
            'email': 'john@example.com',
            'address': '123 Test St',
            'services_provided': 'Test Services'
        }
        self.response = self.client.post(
            reverse('supplier-list'),
            self.supplier_data,
            format="json")

    def test_create_supplier(self):
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Supplier.objects.count(), 1)
        self.assertEqual(Supplier.objects.get().name, 'Test Supplier')

    def test_get_all_suppliers(self):
        response = self.client.get(reverse('supplier-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_supplier_by_id(self):
        supplier = Supplier.objects.get()
        response = self.client.get(reverse('supplier-detail', kwargs={'pk': supplier.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Supplier')

    def test_update_supplier(self):
        supplier = Supplier.objects.get()
        updated_data = {
            'name': 'Updated Supplier',
            'contact_person': 'Jane Doe',
            'phone_number': '0987654321'
        }
        response = self.client.patch(
            reverse('supplier-detail', kwargs={'pk': supplier.id}),
            updated_data,
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Supplier.objects.get().name, 'Updated Supplier')
        self.assertEqual(Supplier.objects.get().contact_person, 'Jane Doe')
        self.assertEqual(Supplier.objects.get().phone_number, '0987654321')

    def test_delete_supplier(self):
        supplier = Supplier.objects.get()
        response = self.client.delete(reverse('supplier-detail', kwargs={'pk': supplier.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Supplier.objects.count(), 0)
        
class InventoryItemTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="Test Category")
        self.supplier = Supplier.objects.create(name="Test Supplier")
        self.item_data = {
            'name': 'Test Item',
            'category': self.category.id,
            'quantity': 50,
            'unit_price': '10.00',
            'supplier': self.supplier.id,
            'reorder_level': 10
        }
        self.response = self.client.post(
            reverse('inventoryitem-list'),
            self.item_data,
            format="json")

    def test_create_inventory_item(self):
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(InventoryItem.objects.count(), 1)
        self.assertEqual(InventoryItem.objects.get().name, 'Test Item')

    def test_get_all_inventory_items(self):
        response = self.client.get(reverse('inventoryitem-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_inventory_item_by_id(self):
        item = InventoryItem.objects.get()
        response = self.client.get(reverse('inventoryitem-detail', kwargs={'pk': item.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Item')

    def test_update_inventory_item(self):
        item = InventoryItem.objects.get()
        updated_data = {'name': 'Updated Item', 'quantity': 60}
        response = self.client.patch(
            reverse('inventoryitem-detail', kwargs={'pk': item.id}),
            updated_data,
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(InventoryItem.objects.get().name, 'Updated Item')
        self.assertEqual(InventoryItem.objects.get().quantity, 60)

    def test_delete_inventory_item(self):
        item = InventoryItem.objects.get()
        response = self.client.delete(reverse('inventoryitem-detail', kwargs={'pk': item.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(InventoryItem.objects.count(), 0)

    def test_restock_inventory_item(self):
        item = InventoryItem.objects.get()
        initial_quantity = item.quantity
        restock_data = {'quantity': 20}
        response = self.client.post(
            reverse('inventoryitem-restock', kwargs={'pk': item.id}),
            restock_data,
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(InventoryItem.objects.get().quantity, initial_quantity + 20)

    def test_low_stock_alert(self):
        # Créer un article avec un stock bas
        InventoryItem.objects.create(
            name='Low Stock Item',
            category=self.category,
            quantity=5,
            unit_price='10.00',
            supplier=self.supplier,
            reorder_level=10
        )
        # Créer un article avec un stock suffisant
        InventoryItem.objects.create(
            name='Normal Stock Item',
            category=self.category,
            quantity=20,
            unit_price='10.00',
            supplier=self.supplier,
            reorder_level=10
        )
        response = self.client.get(reverse('inventoryitem-low-stock'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Low Stock Item')
        
class ItemTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="Test Category", description="Test Description")
        self.item_data = {
            'name': 'Test Item',
            'description': 'Test Item Description',
            'category': self.category.id,
            'quantity': 10,
            'price': '100.00'
        }
        self.response = self.client.post(
            reverse('item-list'),
            self.item_data,
            format="json")

    def test_create_item(self):
        """Test creating a new item"""
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Item.objects.count(), 1)
        self.assertEqual(Item.objects.get().name, 'Test Item')

    def test_get_all_items(self):
        """Test getting all items"""
        # Create another item
        Item.objects.create(name='Another Item', description='Another Description', category=self.category, quantity=5, price=50.00)
        
        response = self.client.get(reverse('item-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Now we have two items

    def test_get_item_by_id(self):
        """Test getting a specific item by ID"""
        item = Item.objects.get()
        response = self.client.get(reverse('item-detail', kwargs={'pk': item.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Item')

    def test_update_item(self):
        """Test updating an existing item"""
        item = Item.objects.get()
        updated_data = {
            'name': 'Updated Item',
            'description': 'Updated Description',
            'quantity': 20,
            'price': '150.00',
            'category': self.category.id  # Inclure la catégorie si nécessaire
        }
        response = self.client.put(
            reverse('item-detail', kwargs={'pk': item.id}),
            updated_data,
            format="json")
        
        # Ajoute cette ligne pour voir l'erreur exacte
        print(response.data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def test_partial_update_item(self):
        """Test partial update of an item"""
        item = Item.objects.get()
        partial_data = {'description': 'Partially Updated Description'}
        response = self.client.patch(
            reverse('item-detail', kwargs={'pk': item.id}),
            partial_data,
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Item.objects.get().description, 'Partially Updated Description')
        self.assertEqual(Item.objects.get().name, 'Test Item')  # Name should remain unchanged

    def test_delete_item(self):
        """Test deleting an item"""
        item = Item.objects.get()
        response = self.client.delete(reverse('item-detail', kwargs={'pk': item.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Item.objects.count(), 0)

    def test_create_invalid_item(self):
        """Test creating a new item with invalid data"""
        invalid_data = {'name': '', 'description': 'Invalid Item', 'category': self.category.id, 'quantity': 5, 'price': '50.00'}
        response = self.client.post(reverse('item-list'), invalid_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_non_existent_item(self):
        """Test updating an item that doesn't exist"""
        non_existent_id = 999
        updated_data = {'name': 'Updated Item', 'description': 'Updated Description', 'quantity': 20, 'price': '150.00'}
        response = self.client.put(
            reverse('item-detail', kwargs={'pk': non_existent_id}),
            updated_data,
            format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_non_existent_item(self):
        """Test deleting an item that doesn't exist"""
        non_existent_id = 999
        response = self.client.delete(reverse('item-detail', kwargs={'pk': non_existent_id}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
class VehicleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.vehicle_data = {
            'vehicle_number': 'V001',
            'type': 'bus',
            'make': 'Mercedes',
            'model': 'Sprinter',
            'year': 2022,
            'capacity': 20,
            'fuel_type': 'diesel',
            'license_plate': 'ABC123',
            'mileage': 0,
            'status': 'active'
        }
        self.response = self.client.post(
            reverse('vehicle-list'),
            self.vehicle_data,
            format="json")

    def test_create_vehicle(self):
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Vehicle.objects.count(), 1)
        self.assertEqual(Vehicle.objects.get().vehicle_number, 'V001')

    def test_get_all_vehicles(self):
        response = self.client.get(reverse('vehicle-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_vehicle_by_id(self):
        vehicle = Vehicle.objects.get()
        response = self.client.get(reverse('vehicle-detail', kwargs={'pk': vehicle.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['vehicle_number'], 'V001')

    def test_update_vehicle(self):
        vehicle = Vehicle.objects.get()
        updated_data = {'make': 'Volvo', 'model': 'XC90'}
        response = self.client.patch(
            reverse('vehicle-detail', kwargs={'pk': vehicle.id}),
            updated_data,
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Vehicle.objects.get().make, 'Volvo')
        self.assertEqual(Vehicle.objects.get().model, 'XC90')

    def test_delete_vehicle(self):
        vehicle = Vehicle.objects.get()
        response = self.client.delete(reverse('vehicle-detail', kwargs={'pk': vehicle.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Vehicle.objects.count(), 0)

    def test_update_vehicle_mileage(self):
        vehicle = Vehicle.objects.get()
        new_mileage = 1000
        response = self.client.patch(
            reverse('vehicle-update-mileage', kwargs={'pk': vehicle.id}),
            {'mileage': new_mileage},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Vehicle.objects.get().mileage, new_mileage)

    def test_change_vehicle_status(self):
        vehicle = Vehicle.objects.get()
        new_status = 'maintenance'
        response = self.client.patch(
            reverse('vehicle-change-status', kwargs={'pk': vehicle.id}),
            {'status': new_status},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Vehicle.objects.get().status, new_status)
        
class VehicleMaintenanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.vehicle = Vehicle.objects.create(
            vehicle_number='V001',
            type='bus',
            make='Mercedes',
            model='Sprinter',
            year=2022,
            capacity=20,
            fuel_type='diesel',
            license_plate='ABC123'
        )
        self.maintenance_data = {
            'vehicle': self.vehicle.id,
            'maintenance_type': 'Oil Change',
            'description': 'Regular oil change',
            'date_performed': '2023-01-01',
            'cost': '100.00',
            'performed_by': 'John Doe',
            'next_maintenance_date': '2023-07-01'
        }
        self.response = self.client.post(
            reverse('vehiclemaintenance-list'),
            self.maintenance_data,
            format="json")

    def test_create_vehicle_maintenance(self):
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(VehicleMaintenance.objects.count(), 1)
        self.assertEqual(VehicleMaintenance.objects.get().maintenance_type, 'Oil Change')

    def test_get_all_maintenances_for_vehicle(self):
        response = self.client.get(
            reverse('vehiclemaintenance-get-for-vehicle') + f'?vehicle_id={self.vehicle.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_update_vehicle_maintenance(self):
        maintenance = VehicleMaintenance.objects.get()
        updated_data = {'cost': '150.00', 'performed_by': 'Jane Doe'}
        response = self.client.patch(
            reverse('vehiclemaintenance-detail', kwargs={'pk': maintenance.id}),
            updated_data,
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(VehicleMaintenance.objects.get().cost, 150.00)
        self.assertEqual(VehicleMaintenance.objects.get().performed_by, 'Jane Doe')

    def test_delete_vehicle_maintenance(self):
        maintenance = VehicleMaintenance.objects.get()
        response = self.client.delete(reverse('vehiclemaintenance-detail', kwargs={'pk': maintenance.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(VehicleMaintenance.objects.count(), 0)

    def test_get_upcoming_maintenances(self):
        # Create a maintenance with a future next_maintenance_date
        VehicleMaintenance.objects.create(
            vehicle=self.vehicle,
            maintenance_type='Tire Change',
            description='Regular tire change',
            date_performed=date.today(),
            cost='200.00',
            performed_by='Bob Smith',
            next_maintenance_date=date.today() + timedelta(days=30)
        )
        response = self.client.get(reverse('vehiclemaintenance-upcoming-maintenances'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['maintenance_type'], 'Tire Change')
        
        
class InventoryUtilsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="Test Category")
        self.supplier = Supplier.objects.create(name="Test Supplier")
        self.item1 = InventoryItem.objects.create(
            name="Item 1",
            category=self.category,
            quantity=10,
            unit_price=5.00,
            supplier=self.supplier,
            reorder_level=5
        )
        self.item2 = InventoryItem.objects.create(
            name="Item 2",
            category=self.category,
            quantity=3,
            unit_price=10.00,
            supplier=self.supplier,
            reorder_level=5
        )
        self.vehicle = Vehicle.objects.create(
            vehicle_number='V001',
            type='bus',
            make='Mercedes',
            model='Sprinter',
            year=2022,
            capacity=20,
            fuel_type='diesel',
            license_plate='ABC123'
        )
        self.maintenance1 = VehicleMaintenance.objects.create(
            vehicle=self.vehicle,
            maintenance_type='Oil Change',
            description='Regular oil change',
            date_performed=date.today() - timedelta(days=30),
            cost=100.00,
            performed_by='John Doe'
        )
        self.maintenance2 = VehicleMaintenance.objects.create(
            vehicle=self.vehicle,
            maintenance_type='Tire Change',
            description='Regular tire change',
            date_performed=date.today() - timedelta(days=15),
            cost=200.00,
            performed_by='Jane Doe'
        )

    def test_calculate_total_inventory_value(self):
        response = self.client.get(reverse('inventory-utils') + '?action=total_value')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_value'], 80.00)  # (10 * 5.00) + (3 * 10.00)

    def test_generate_inventory_report(self):
        response = self.client.get(reverse('inventory-utils') + '?action=inventory_report')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['name'], 'Item 1')
        self.assertEqual(response.data[1]['name'], 'Item 2')
        self.assertFalse(response.data[0]['is_low_stock'])
        self.assertTrue(response.data[1]['is_low_stock'])

    def test_generate_low_stock_alert(self):
        response = self.client.get(reverse('inventory-utils') + '?action=low_stock_alert')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Item 2')

    def test_calculate_vehicle_maintenance_costs(self):
        start_date = date.today() - timedelta(days=60)
        end_date = date.today()
        response = self.client.get(
            reverse('inventory-utils') + 
            f'?action=maintenance_costs&vehicle_id={self.vehicle.id}&start_date={start_date}&end_date={end_date}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_cost'], 300.00)  # 100.00 + 200.00