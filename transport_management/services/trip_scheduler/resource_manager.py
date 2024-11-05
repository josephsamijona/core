# transport_management/services/trip_scheduler/resource_manager.py

from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from ...models import (
    ResourceAvailability, 
    Driver, 
    DriverSchedule, 
    DriverVehicleAssignment
)
from ..base.service_base import ServiceBase

class ResourceManager(ServiceBase):
    def __init__(self):
        super().__init__()
        self.current_date = timezone.now().date()

    def check_resource_availability(self, start_time, end_time, route=None):
        """
        Vérifie la disponibilité des ressources pour une période donnée
        """
        try:
            available_assignments = self._get_available_driver_assignments(start_time, end_time, route)

            return {
                'has_resources': bool(available_assignments),
                'available_assignments': available_assignments
            }
        except Exception as e:
            self.log_error(f"Error checking resource availability: {str(e)}", exc=e)
            return {'has_resources': False, 'available_assignments': []}

    def _get_available_driver_assignments(self, start_time, end_time, route=None):
        """
        Trouve les assignations chauffeur-véhicule disponibles pour la période donnée
        """
        try:
            # 1. Vérifier les assignations véhicule-chauffeur actives
            available_assignments = DriverVehicleAssignment.objects.filter(
                assigned_from__lte=start_time,
                assigned_until__gte=end_time,
                status='active'
            ).select_related('driver', 'vehicle')

            # 2. Vérifier ResourceAvailability pour les chauffeurs
            available_driver_ids = ResourceAvailability.objects.filter(
                resource_type='driver',
                date=start_time.date(),
                start_time__lte=start_time.time(),
                end_time__gte=end_time.time(),
                is_available=True,
                status='available'
            ).values_list('driver_id', flat=True)

            available_assignments = available_assignments.filter(
                driver_id__in=available_driver_ids
            )

            # 3. Vérifier le DriverSchedule
            busy_driver_ids = DriverSchedule.objects.filter(
                shift_start__lt=end_time,
                shift_end__gt=start_time,
                status__in=['scheduled', 'in_progress']
            ).values_list('driver_id', flat=True)

            available_assignments = available_assignments.exclude(
                driver_id__in=busy_driver_ids
            )

            # 4. Vérifier le statut des chauffeurs
            available_assignments = available_assignments.filter(
                driver__employment_status='active',
                driver__availability_status='available'
            )

            # 5. Appliquer les filtres de route si nécessaire
            if route:
                available_assignments = available_assignments.filter(
                    driver__preferred_routes=route
                ).exclude(
                    driver__route_restrictions__contains=[route.id]
                )

            return available_assignments.order_by('driver__total_hours')

        except Exception as e:
            self.log_error(f"Error getting available driver assignments: {str(e)}", exc=e)
            return []

    def allocate_resources(self, trip, start_time, end_time):
        """
        Alloue les ressources pour un trip
        """
        try:
            with transaction.atomic():
                # 1. Trouver les assignations disponibles
                available_assignments = self._get_available_driver_assignments(
                    start_time, 
                    end_time, 
                    trip.route
                )

                if not available_assignments.exists():
                    raise ValueError("No driver assignments available for the trip")

                # 2. Sélectionner la meilleure assignation
                selected_assignment = available_assignments.first()

                # 3. Créer le DriverSchedule
                schedule = DriverSchedule.objects.create(
                    driver=selected_assignment.driver,
                    shift_start=start_time,
                    shift_end=end_time,
                    status='scheduled'
                )

                # 4. Mettre à jour la disponibilité du chauffeur
                ResourceAvailability.objects.filter(
                    resource_type='driver',
                    driver=selected_assignment.driver,
                    date=start_time.date()
                ).update(status='reserved')

                return {
                    'assignment': selected_assignment,
                    'schedule': schedule
                }

        except Exception as e:
            self.log_error(f"Error allocating resources: {str(e)}", exc=e)
            raise

    def deallocate_resources(self, trip):
        """
        Libère les ressources d'un trip
        """
        try:
            with transaction.atomic():
                # Libérer le DriverSchedule
                DriverSchedule.objects.filter(
                    driver=trip.driver,
                    shift_start=trip.planned_departure
                ).update(status='cancelled')

                # Mettre à jour la disponibilité du chauffeur
                ResourceAvailability.objects.filter(
                    resource_type='driver',
                    driver=trip.driver,
                    date=trip.planned_departure.date()
                ).update(status='available')

        except Exception as e:
            self.log_error(f"Error deallocating resources: {str(e)}", exc=e)
            raise