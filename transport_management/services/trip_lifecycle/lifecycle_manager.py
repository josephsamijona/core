# transport_management/services/trip_lifecycle/lifecycle_manager.py

from math import atan2, cos, radians, sin, sqrt
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q
from ...models import Trip, BusPosition, Stop, EventLog
from ..base.service_base import ServiceBase

class TripLifecycleManager(ServiceBase):
    def __init__(self):
        super().__init__()

    def process_lifecycle_updates(self):
        """
        Vérifie et met à jour le statut des trips en cours
        Cette méthode sera appelée périodiquement (par ex. toutes les minutes)
        """
        try:
            self._start_pending_trips()
            self._update_active_trips()
            self._check_completed_trips()
        except Exception as e:
            self.log_error(f"Error processing lifecycle updates: {str(e)}", exc=e)

    def _start_pending_trips(self):
        """Démarre les trips qui doivent commencer"""
        try:
            # Trouver les trips planifiés qui devraient démarrer
            pending_trips = Trip.objects.filter(
                status='planned',
                planned_departure__lte=timezone.now() + timedelta(minutes=5)
            )

            for trip in pending_trips:
                self._check_and_start_trip(trip)

        except Exception as e:
            self.log_error(f"Error starting pending trips: {str(e)}", exc=e)

    def _check_and_start_trip(self, trip):
        """Vérifie les conditions et démarre un trip"""
        try:
            # 1. Vérifier la position du bus au départ
            start_position = self._verify_start_position(trip)
            if not start_position:
                self.log_warning(f"Trip {trip.id} cannot start - Vehicle not at start position")
                return

            # 2. Vérifier que le chauffeur est présent via son mobile
            if not self._verify_driver_presence(trip):
                self.log_warning(f"Trip {trip.id} cannot start - Driver not present")
                return

            # 3. Démarrer le trip
            with transaction.atomic():
                trip.status = 'in_progress'
                trip.actual_start_time = timezone.now()
                trip.save()

                # Créer un événement de démarrage
                EventLog.objects.create(
                    trip=trip,
                    event_type='trip_start',
                    description='Trip started automatically',
                    timestamp=timezone.now()
                )

                self.log_info(f"Trip {trip.id} started successfully")

        except Exception as e:
            self.log_error(f"Error starting trip {trip.id}: {str(e)}", exc=e)

    def _verify_start_position(self, trip):
        """Vérifie si le bus est à la position de départ"""
        try:
            # Obtenir la dernière position connue
            latest_position = BusPosition.objects.filter(
                trip=trip
            ).order_by('-timestamp').first()

            if not latest_position:
                return False

            # Vérifier la distance par rapport au point de départ
            start_stop = trip.route.stops.first()  # Supposons que le premier arrêt est le départ
            if not start_stop:
                return False

            # Calculer la distance
            distance = self._calculate_distance(
                latest_position.latitude, 
                latest_position.longitude,
                start_stop.latitude,
                start_stop.longitude
            )

            # Tolérance de 100 mètres
            return distance <= 0.1

        except Exception as e:
            self.log_error(f"Error verifying start position: {str(e)}", exc=e)
            return False

    def _verify_driver_presence(self, trip):
        """Vérifie si le chauffeur est présent via son mobile"""
        # Vérifier la dernière activité du mobile dans les 5 dernières minutes
        last_position = BusPosition.objects.filter(
            trip=trip,
            data_source='mobile_android'
        ).order_by('-timestamp').first()

        if not last_position:
            return False

        return (timezone.now() - last_position.timestamp) <= timedelta(minutes=5)

    def _update_active_trips(self):
        """Met à jour le statut des trips en cours"""
        try:
            active_trips = Trip.objects.filter(status='in_progress')
            
            for trip in active_trips:
                self._process_active_trip(trip)

        except Exception as e:
            self.log_error(f"Error updating active trips: {str(e)}", exc=e)

    def _process_active_trip(self, trip):
        """Traite un trip actif"""
        try:
            latest_position = BusPosition.objects.filter(
                trip=trip
            ).order_by('-timestamp').first()

            if not latest_position:
                return

            # 1. Vérifier si le bus est arrêté à un stop
            current_stop = self._check_current_stop(trip, latest_position)
            if current_stop:
                self._process_stop_arrival(trip, current_stop)

            # 2. Vérifier les déviations de route
            if not self._verify_route_adherence(trip, latest_position):
                self._handle_route_deviation(trip, latest_position)

            # 3. Mettre à jour les estimations
            self._update_trip_progress(trip, latest_position)

        except Exception as e:
            self.log_error(f"Error processing active trip {trip.id}: {str(e)}", exc=e)

    def _check_completed_trips(self):
        """Vérifie si des trips doivent être marqués comme terminés"""
        try:
            active_trips = Trip.objects.filter(
                status='in_progress',
                planned_arrival__lte=timezone.now()
            )

            for trip in active_trips:
                self._check_trip_completion(trip)

        except Exception as e:
            self.log_error(f"Error checking completed trips: {str(e)}", exc=e)

    def _check_trip_completion(self, trip):
        """Vérifie si un trip est terminé"""
        try:
            latest_position = BusPosition.objects.filter(
                trip=trip
            ).order_by('-timestamp').first()

            if not latest_position:
                return

            # Vérifier si le bus est à l'arrêt final
            final_stop = trip.route.stops.last()
            if not final_stop:
                return

            distance_to_final = self._calculate_distance(
                latest_position.latitude,
                latest_position.longitude,
                final_stop.latitude,
                final_stop.longitude
            )

            # Si le bus est à l'arrêt final
            if distance_to_final <= 0.1 and not latest_position.is_moving:
                self._complete_trip(trip)

        except Exception as e:
            self.log_error(f"Error checking trip completion {trip.id}: {str(e)}", exc=e)

    def _complete_trip(self, trip):
        """Marque un trip comme terminé"""
        try:
            with transaction.atomic():
                trip.status = 'completed'
                trip.actual_end_time = timezone.now()
                trip.save()

                EventLog.objects.create(
                    trip=trip,
                    event_type='trip_end',
                    description='Trip completed automatically',
                    timestamp=timezone.now()
                )

                self.log_info(f"Trip {trip.id} completed successfully")

        except Exception as e:
            self.log_error(f"Error completing trip {trip.id}: {str(e)}", exc=e)

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calcule la distance entre deux points GPS"""
        R = 6371  # Rayon de la Terre en km
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c

    def _process_stop_arrival(self, trip, stop):
        """Traite l'arrivée à un arrêt"""
        try:
            EventLog.objects.create(
                trip=trip,
                event_type='stop_arrival',
                description=f'Arrived at stop: {stop.name}',
                timestamp=timezone.now()
            )

        except Exception as e:
            self.log_error(f"Error processing stop arrival: {str(e)}", exc=e)

    def _verify_route_adherence(self, trip, position):
        """Vérifie si le bus suit bien l'itinéraire"""
        # À implémenter selon vos besoins
        return True

    def _handle_route_deviation(self, trip, position):
        """Gère une déviation de route"""
        try:
            EventLog.objects.create(
                trip=trip,
                event_type='route_deviation',
                description='Vehicle deviated from planned route',
                timestamp=timezone.now()
            )

        except Exception as e:
            self.log_error(f"Error handling route deviation: {str(e)}", exc=e)

    def _update_trip_progress(self, trip, position):
        """Met à jour la progression du trip"""
        try:
            # Calculer le pourcentage de progression
            total_stops = trip.route.stops.count()
            stops_visited = EventLog.objects.filter(
                trip=trip,
                event_type='stop_arrival'
            ).count()

            progress = (stops_visited / total_stops * 100) if total_stops > 0 else 0
            
            trip.progress_percentage = progress
            trip.save()

        except Exception as e:
            self.log_error(f"Error updating trip progress: {str(e)}", exc=e)