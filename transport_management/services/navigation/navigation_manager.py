# transport_management/services/navigation/navigation_manager.py

from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Avg
from math import degrees, radians, sin, cos, sqrt, atan2
from ...models import Trip, BusPosition, Stop, Route, EventLog
from ..base.service_base import ServiceBase

class NavigationManager(ServiceBase):
    def __init__(self):
        super().__init__()
        self.MAX_DEVIATION_DISTANCE = 0.100  # 100 mètres
        self.ROUTE_CHECK_INTERVAL = 30  # secondes
        self.REROUTE_THRESHOLD = 3  # nombre de déviations avant recalcul

    def process_navigation_update(self, trip_id):
        """
        Traite les mises à jour de navigation pour un trip
        """
        try:
            trip = Trip.objects.get(id=trip_id)
            if trip.status not in ['in_progress', 'delayed']:
                return

            latest_position = self._get_latest_position(trip)
            if not latest_position:
                return

            # 1. Vérifier la conformité à l'itinéraire
            route_check = self._check_route_conformity(trip, latest_position)
            
            # 2. Mettre à jour les estimations
            if route_check['is_conforming']:
                self._update_eta_estimates(trip, latest_position)
            else:
                self._handle_route_deviation(trip, latest_position, route_check)

        except Trip.DoesNotExist:
            self.log_error(f"Trip {trip_id} not found")
        except Exception as e:
            self.log_error(f"Error processing navigation update: {str(e)}", exc=e)

    def _get_latest_position(self, trip):
        """Récupère la dernière position valide"""
        try:
            latest = BusPosition.objects.filter(
                trip=trip,
                position_status='active'
            ).order_by('-timestamp').first()

            if not latest:
                return None

            # Vérifier si la position n'est pas trop ancienne
            if (timezone.now() - latest.timestamp) > timedelta(seconds=self.ROUTE_CHECK_INTERVAL):
                return None

            return latest

        except Exception as e:
            self.log_error(f"Error getting latest position: {str(e)}", exc=e)
            return None

    def _check_route_conformity(self, trip, current_position):
        """
        Vérifie si le bus suit bien l'itinéraire prévu
        """
        try:
            # 1. Obtenir le segment de route actuel
            current_segment = self._get_current_route_segment(trip, current_position)
            if not current_segment:
                return {'is_conforming': False, 'deviation_type': 'unknown_segment'}

            # 2. Calculer la distance par rapport au segment
            deviation = self._calculate_deviation_from_segment(
                current_position,
                current_segment
            )

            # 3. Vérifier la direction
            direction_check = self._check_direction_conformity(
                current_position,
                current_segment
            )

            return {
                'is_conforming': deviation <= self.MAX_DEVIATION_DISTANCE and direction_check,
                'deviation_distance': deviation,
                'current_segment': current_segment,
                'deviation_type': self._classify_deviation(deviation, direction_check)
            }

        except Exception as e:
            self.log_error(f"Error checking route conformity: {str(e)}", exc=e)
            return {'is_conforming': False, 'deviation_type': 'error'}

    def _get_current_route_segment(self, trip, position):
        """
        Détermine le segment de route actuel
        """
        try:
            # Obtenir les deux derniers stops visités
            visited_stops = EventLog.objects.filter(
                trip=trip,
                event_type='stop_arrival'
            ).order_by('-timestamp')[:2]

            if len(visited_stops) < 2:
                # Cas spécial pour le début du trajet
                first_stop = trip.route.stops.first()
                second_stop = trip.route.stops.all()[1]
            else:
                first_stop = visited_stops[1].related_stop
                second_stop = visited_stops[0].related_stop

            return {
                'start': first_stop,
                'end': second_stop,
                'expected_direction': self._calculate_bearing(
                    first_stop.latitude, first_stop.longitude,
                    second_stop.latitude, second_stop.longitude
                )
            }

        except Exception as e:
            self.log_error(f"Error getting current route segment: {str(e)}", exc=e)
            return None

    def _calculate_deviation_from_segment(self, position, segment):
        """
        Calcule la distance entre la position actuelle et le segment de route
        """
        try:
            # Calculer la distance perpendiculaire au segment
            start = segment['start']
            end = segment['end']
            
            # Formule de la distance point-ligne
            x = position.longitude
            y = position.latitude
            x1 = float(start.longitude)
            y1 = float(start.latitude)
            x2 = float(end.longitude)
            y2 = float(end.latitude)

            numerator = abs((y2-y1)*x - (x2-x1)*y + x2*y1 - y2*x1)
            denominator = sqrt((y2-y1)**2 + (x2-x1)**2)
            
            if denominator == 0:
                return float('inf')
                
            return numerator/denominator

        except Exception as e:
            self.log_error(f"Error calculating deviation: {str(e)}", exc=e)
            return float('inf')

    def _check_direction_conformity(self, position, segment):
        """
        Vérifie si le bus se déplace dans la bonne direction
        """
        try:
            if not position.heading:
                return True  # Pas d'info de direction disponible

            expected_direction = segment['expected_direction']
            current_direction = position.heading

            # Permettre une marge d'erreur de 45 degrés
            difference = abs(expected_direction - current_direction)
            return difference <= 45 or difference >= 315

        except Exception as e:
            self.log_error(f"Error checking direction: {str(e)}", exc=e)
            return True

    def _calculate_bearing(self, lat1, lon1, lat2, lon2):
        """
        Calcule la direction entre deux points en degrés
        """
        try:
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            d_lon = lon2 - lon1

            y = sin(d_lon) * cos(lat2)
            x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(d_lon)
            
            bearing = atan2(y, x)
            return (degrees(bearing) + 360) % 360

        except Exception as e:
            self.log_error(f"Error calculating bearing: {str(e)}", exc=e)
            return 0

    def _update_eta_estimates(self, trip, position):
        """
        Met à jour les estimations de temps d'arrivée
        """
        try:
            # 1. Obtenir les arrêts restants
            remaining_stops = trip.route.stops.filter(
                sequence__gt=position.last_stop_sequence
            ).order_by('sequence')

            # 2. Calculer la vitesse moyenne récente
            avg_speed = trip.busposition_set.filter(
                timestamp__gte=timezone.now() - timedelta(minutes=15),
                is_moving=True
            ).aggregate(Avg('speed'))['speed__avg'] or position.speed

            # 3. Mettre à jour les ETA pour chaque arrêt
            for stop in remaining_stops:
                distance = self._calculate_distance_to_stop(position, stop)
                estimated_time = self._calculate_travel_time(distance, avg_speed)
                
                self._update_stop_eta(trip, stop, estimated_time)

        except Exception as e:
            self.log_error(f"Error updating ETA estimates: {str(e)}", exc=e)

    def _handle_route_deviation(self, trip, position, route_check):
        """
        Gère une déviation détectée
        """
        try:
            # 1. Enregistrer la déviation
            EventLog.objects.create(
                trip=trip,
                event_type='route_deviation',
                description=f"Deviation detected: {route_check['deviation_type']}",
                details={
                    'deviation_distance': route_check['deviation_distance'],
                    'position': {
                        'lat': position.latitude,
                        'lon': position.longitude
                    }
                }
            )

            # 2. Vérifier si un recalcul est nécessaire
            recent_deviations = EventLog.objects.filter(
                trip=trip,
                event_type='route_deviation',
                timestamp__gte=timezone.now() - timedelta(minutes=5)
            ).count()

            if recent_deviations >= self.REROUTE_THRESHOLD:
                self._recalculate_route(trip, position)

        except Exception as e:
            self.log_error(f"Error handling route deviation: {str(e)}", exc=e)

    def _recalculate_route(self, trip, position):
        """
        Recalcule l'itinéraire à partir de la position actuelle
        """
        try:
            # 1. Trouver le prochain arrêt atteignable
            next_stop = self._find_next_reachable_stop(trip, position)
            if not next_stop:
                return

            # 2. Mettre à jour les estimations
            self._update_eta_estimates(trip, position)

            # 3. Notifier du recalcul
            EventLog.objects.create(
                trip=trip,
                event_type='route_recalculation',
                description=f"Route recalculated to next stop: {next_stop.name}"
            )

        except Exception as e:
            self.log_error(f"Error recalculating route: {str(e)}", exc=e)

    def _find_next_reachable_stop(self, trip, position):
        """
        Trouve le prochain arrêt atteignable après une déviation
        """
        # À implémenter selon vos besoins
        pass

    def _classify_deviation(self, deviation_distance, direction_ok):
        """
        Classifie le type de déviation
        """
        if direction_ok:
            if deviation_distance <= self.MAX_DEVIATION_DISTANCE:
                return 'minor'
            elif deviation_distance <= self.MAX_DEVIATION_DISTANCE * 2:
                return 'moderate'
            else:
                return 'major'
        else:
            return 'wrong_direction'