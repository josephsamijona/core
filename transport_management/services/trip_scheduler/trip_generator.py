# transport_management/services/trip_scheduler/trip_generator.py

from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from ...models import Schedule, Trip, DriverVehicleAssignment, ResourceAvailability
from ..base.service_base import ServiceBase
from .resource_manager import ResourceManager

class TripGeneratorService(ServiceBase):
    def __init__(self):
        super().__init__()
        self.target_date = timezone.now().date()
        self.resource_manager = ResourceManager()

    def generate_daily_trips(self, target_date=None):
        """
        Génère les trips pour une journée donnée basée sur les schedules actifs
        """
        if target_date:
            self.target_date = target_date

        try:
            with transaction.atomic():
                # 1. Récupérer tous les schedules actifs pour ce jour
                active_schedules = self._get_active_schedules()
                
                if not active_schedules.exists():
                    self.log_info(f"No active schedules found for {self.target_date}")
                    return []

                # 2. Pour chaque schedule, générer les trips nécessaires
                generated_trips = []
                for schedule in active_schedules:
                    trips = self._generate_trips_for_schedule(schedule)
                    generated_trips.extend(trips)

                self.log_info(f"Generated {len(generated_trips)} trips for {self.target_date}")
                return generated_trips

        except Exception as e:
            self.log_error(f"Error generating daily trips: {str(e)}", exc=e)
            raise

    def _get_active_schedules(self):
        """Récupère les schedules actifs pour le jour cible"""
        day_name = self.target_date.strftime('%A').lower()
        
        return Schedule.objects.filter(
            is_active=True,
            status='active',
            day_of_week=day_name,
            start_date__lte=self.target_date,
            end_date__gte=self.target_date
        )

    def _generate_trips_for_schedule(self, schedule):
        """Génère les trips pour un schedule donné"""
        # Valider les conditions initiales
        if not self._validate_schedule_conditions(schedule):
            self.log_warning(f"Schedule {schedule.id} failed validation")
            return []

        # Générer les timepoints
        schedule.generate_timepoints_for_date(self.target_date)
        
        trips = []
        for timepoint in schedule.timepoints:
            # Pour chaque timepoint, créer un trip si les ressources sont disponibles
            try:
                trip = self._create_trip_for_timepoint(schedule, timepoint)
                if trip:
                    trips.append(trip)
            except Exception as e:
                self.log_error(f"Error creating trip for timepoint {timepoint}: {str(e)}", exc=e)

        return trips

    def _validate_schedule_conditions(self, schedule):
        """Valide les conditions initiales pour un schedule"""
        try:
            # 1. Vérifier les conditions de base
            if not schedule.is_current_version:
                self.log_warning(f"Schedule {schedule.id} is not the current version")
                return False

            # 2. Vérifier la disponibilité des ressources pour la journée
            departure_time = datetime.combine(self.target_date, schedule.start_time)
            end_time = datetime.combine(self.target_date, schedule.end_time)
            
            resource_check = self.resource_manager.check_resource_availability(
                schedule.route,
                schedule.destination,  # Passer la destination pour la vérification des ressources
                departure_time,
                end_time
            )

            if not resource_check['has_resources']:
                self.log_warning(f"No resources available for schedule {schedule.id}")
                return False

            return True

        except Exception as e:
            self.log_error(f"Error validating schedule conditions: {str(e)}", exc=e)
            return False

    def _create_trip_for_timepoint(self, schedule, timepoint):
        """Crée un trip pour un timepoint spécifique"""
        try:
            with transaction.atomic():
                departure_time = datetime.combine(self.target_date, timepoint)
                is_peak = schedule.is_peak_hour(timepoint.time())
                trip_duration = self._calculate_trip_duration(schedule, is_peak)
                arrival_time = departure_time + trip_duration

                # Vérifier que l'arrivée prévue ne dépasse pas l'heure de fin du schedule
                schedule_end_datetime = datetime.combine(self.target_date, schedule.end_time)
                if arrival_time > schedule_end_datetime:
                    self.log_warning(f"Trip arrival time {arrival_time} exceeds schedule end time {schedule_end_datetime}. Skipping trip.")
                    return None

                # 1. Vérifier et allouer les ressources
                resource_allocation = self.resource_manager.allocate_resources(
                    schedule.route,
                    schedule.destination,  # Passer la destination pour l'allocation des ressources
                    departure_time,
                    arrival_time
                )

                if not resource_allocation:
                    self.log_warning(f"Could not allocate resources for timepoint {timepoint}")
                    return None

                assignment = resource_allocation['assignment']
                driver_schedule = resource_allocation['schedule']

                # 2. Créer le trip
                trip = Trip.objects.create(
                    schedule=schedule,
                    route=schedule.route,
                    destination=schedule.destination,  # Utiliser la destination du schedule
                    driver=assignment.driver,
                    vehicle=assignment.vehicle,
                    trip_date=self.target_date,
                    planned_departure=departure_time,
                    planned_arrival=arrival_time,
                    status='planned',
                    trip_type='regular',
                    priority='medium',
                    max_capacity=assignment.vehicle.capacity if hasattr(assignment.vehicle, 'capacity') else None,
                    origin=schedule.route.start_point if hasattr(schedule.route, 'start_point') else None,
                )

                # 3. Enregistrer les références croisées
                driver_schedule.trip = trip
                driver_schedule.save()

                # 4. Log de l'action
                self.log_info(f"Created trip {trip.id} for schedule {schedule.id} at {timepoint}")

                return trip

        except Exception as e:
            self.log_error(f"Error creating trip: {str(e)}", exc=e)
            return None

    def _calculate_trip_duration(self, schedule, is_peak_hour):
        """Calcule la durée estimée du trip en fonction des conditions"""
        # Calcul basé sur la route et les conditions
        base_duration_minutes = getattr(schedule.route, 'estimated_duration', 30)
        buffer_time = 10  # Minutes

        # Ajustement en fonction des heures de pointe
        if is_peak_hour:
            rush_adjustment = schedule.rush_hour_adjustment
            trip_duration_minutes = base_duration_minutes + rush_adjustment + buffer_time
        else:
            trip_duration_minutes = base_duration_minutes + buffer_time

        return timedelta(minutes=trip_duration_minutes)

    def cancel_trip(self, trip_id, reason):
        """Annule un trip et libère ses ressources"""
        try:
            with transaction.atomic():
                trip = Trip.objects.get(id=trip_id)
                trip.status = 'cancelled'
                trip.modification_reason = reason
                trip.save()

                # Libérer les ressources
                self.resource_manager.deallocate_resources(trip)

                self.log_info(f"Cancelled trip {trip_id} - Reason: {reason}")

        except Trip.DoesNotExist:
            self.log_error(f"Trip {trip_id} not found")
        except Exception as e:
            self.log_error(f"Error cancelling trip: {str(e)}", exc=e)
            raise

    def reschedule_trip(self, trip_id, new_departure_time):
        """Replanifie un trip pour un nouveau horaire"""
        try:
            with transaction.atomic():
                trip = Trip.objects.get(id=trip_id)
                
                # Calculer le nouvel horaire
                is_peak = trip.schedule.is_peak_hour(new_departure_time.time())
                trip_duration = self._calculate_trip_duration(trip.schedule, is_peak)
                new_end_time = new_departure_time + trip_duration

                # Vérifier que l'arrivée prévue ne dépasse pas l'heure de fin du schedule
                schedule_end_datetime = datetime.combine(trip.trip_date, trip.schedule.end_time)
                if new_end_time > schedule_end_datetime:
                    raise ValueError(f"New arrival time {new_end_time} exceeds schedule end time {schedule_end_datetime}.")

                # Vérifier la disponibilité des ressources
                resource_check = self.resource_manager.check_resource_availability(
                    trip.route,
                    trip.destination,  # Passer la destination pour la vérification des ressources
                    new_departure_time,
                    new_end_time
                )

                if not resource_check['has_resources']:
                    raise ValueError("No resources available for rescheduling")

                # Libérer les ressources actuelles
                self.resource_manager.deallocate_resources(trip)

                # Allouer les nouvelles ressources
                new_allocation = self.resource_manager.allocate_resources(
                    trip.route,
                    trip.destination,  # Passer la destination pour l'allocation des ressources
                    new_departure_time,
                    new_end_time
                )

                if not new_allocation:
                    raise ValueError("Could not allocate resources for rescheduled trip")

                # Mettre à jour le trip
                trip.planned_departure = new_departure_time
                trip.planned_arrival = new_end_time
                trip.driver = new_allocation['assignment'].driver
                trip.vehicle = new_allocation['assignment'].vehicle
                trip.status = 'rescheduled'
                trip.save()

                self.log_info(f"Rescheduled trip {trip_id} to {new_departure_time}")

        except Trip.DoesNotExist:
            self.log_error(f"Trip {trip_id} not found")
        except Exception as e:
            self.log_error(f"Error rescheduling trip: {str(e)}", exc=e)
            raise
