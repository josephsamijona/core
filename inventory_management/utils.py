# inventory_management/utils.py

from django.db.models import Sum, F
from django.utils import timezone
from .models import InventoryItem, Vehicle, VehicleMaintenance

def calculate_total_inventory_value():
    return InventoryItem.objects.aggregate(
        total_value=Sum(F('quantity') * F('unit_price'))
    )['total_value'] or 0

def generate_inventory_report():
    items = InventoryItem.objects.all()
    report = []
    for item in items:
        report.append({
            'name': item.name,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_value': item.quantity * item.unit_price,
            'supplier': item.supplier.name if item.supplier else 'N/A',
            'is_low_stock': item.is_low_stock()
        })
    return report

def generate_low_stock_alert():
    return list(InventoryItem.objects.filter(quantity__lte=F('reorder_level')).values(
        'name', 'quantity', 'reorder_level'
    ))

def calculate_vehicle_maintenance_costs(vehicle_id, start_date, end_date):
    return VehicleMaintenance.objects.filter(
        vehicle_id=vehicle_id,
        date_performed__range=[start_date, end_date]
    ).aggregate(total_cost=Sum('cost'))['total_cost'] or 0