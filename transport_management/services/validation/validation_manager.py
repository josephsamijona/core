# transport_management/services/validation/validation_manager.py

from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Avg, Q
from ...models import Trip, BusPosition, Stop, EventLog, Route
from ..base.service_base import ServiceBase

class ValidationManager(ServiceBase):
    def __init__(self):
        super().__init__()
        # Seuils de validation GPS
        self.MIN_ACCURACY = 20.0  # mètres
        self.MAX_SPEED = 90.0  # km/h
        self.MIN_SPEED = 0.0  # km/h
        self.MAX_ACCELERATION = 3.0  # m/s²
        self.MIN_SATELLITES = 4
        self.MAX_HDOP = 5.0  # Dilution horizontale de la précision

        # Seuils de service
        self.MAX_STOP_DURATION = 300  # secondes (5 minutes)
        self.MIN_STOP_DURATION = 15  # secondes
        self.STOP_RADIUS = 50  # mètres
        self.MAX_ROUTE_DEVIATION = 100  # mètres

    def validate_position(self, position_data, trip_id):
        """Valide une nouvelle position GPS"""
        try:
            validation_results = {
                'is_valid': True,
                'errors': [],
                'warnings': []
            }

            # 1. Validation GPS de base
            self._validate_gps_basics(position_data, validation_results)
            
            # 2. Validation de la cohérence
            if validation_results['is_valid']:
                self._validate_position_coherence(position_data, trip_id, validation_results)
            
            # 3. Validation du service
            if validation_results['is_valid']:
                self._validate_service_rules(position_data, trip_id, validation_results)

            return validation_results

        except Exception as e:
            self.log_error(f"Error validating position: {str(e)}", exc=e)
            return {'is_valid': False, 'errors': [str(e)], 'warnings': []}

    def _validate_gps_basics(self, data, results):
        """Valide les données GPS de base"""
        try:
            # Vérification de la précision
            if data.get('accuracy', float('inf')) > self.MIN_ACCURACY:
                results['warnings'].append('Low GPS accuracy')

            # Vérification du HDOP
            if data.get('hdop', float('inf')) > self.MAX_HDOP:
                results['warnings'].append('High HDOP value')

            # Vérification du nombre de satellites
            if data.get('satellites', 0) < self.MIN_SATELLITES:
                results['warnings'].append('Insufficient satellites')

            # Vérification des coordonnées
            lat = float(data.get('latitude', 0))
            lon = float(data.get('longitude', 0))
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                results['errors'].append('Invalid coordinates')
                results['is_valid'] = False

        except Exception as e:
            results['errors'].append(f'GPS validation error: {str(e)}')
            results['is_valid'] = False

    def _validate_position_coherence(self, data, trip_id, results):
        """Valide la cohérence de la position"""
        try:
            # Récupérer la dernière position valide
            last_position = BusPosition.objects.filter(
                trip_id=trip_id,
                is_valid=True
            ).order_by('-timestamp').first()

            if last_position:
                # 1. Vérification de la vitesse
                speed = float(data.get('speed', 0))
                if not self.MIN_SPEED <= speed <= self.MAX_SPEED:
                    results['errors'].append('Speed out of valid range')
                    results['is_valid'] = False

                # 2. Vérification de l'accélération
                if self._calculate_acceleration(data, last_position) > self.MAX_ACCELERATION:
                    results['warnings'].append('Abnormal acceleration detected')

                # 3. Vérification de la distance
                if self._detect_position_jump(data, last_position):
                    results['errors'].append('Unrealistic position jump detected')
                    results['is_valid'] = False

        except Exception as e:
            results['errors'].append(f'Coherence validation error: {str(e)}')
            results['is_valid'] = False

    def _validate_service_rules(self, data, trip_id, results):
        """Valide les règles de service"""
        try:
            trip = Trip.objects.get(id=trip_id)

            # 1. Validation de l'itinéraire
            route_deviation = self._check_route_deviation(data, trip)
            if route_deviation > self.MAX_ROUTE_DEVIATION:
                results['warnings'].append(f'Route deviation: {route_deviation:.2f}m')

            # 2. Validation des arrêts
            if self._is_at_stop(data, trip):
                self._validate_stop_rules(data, trip, results)

            # 3. Validation de la vitesse selon le contexte
            self._validate_contextual_speed(data, trip, results)

        except Trip.DoesNotExist:
            results['errors'].append('Trip not found')
            results['is_valid'] = False
        except Exception as e:
            results['errors'].append(f'Service validation error: {str(e)}')
            results['is_valid'] = False

    def _calculate_acceleration(self, current_data, last_position):
        """Calcule l'accélération entre deux positions"""
        try:
            current_speed = float(current_data.get('speed', 0))
            last_speed = float(last_position.speed)
            time_diff = (timezone.now() - last_position.timestamp).total_seconds()

            if time_diff > 0:
                return abs(current_speed - last_speed) / time_diff
            return 0

        except Exception as e:
            self.log_error(f"Error calculating acceleration: {str(e)}", exc=e)
            return 0

    def _detect_position_jump(self, current_data, last_position):
        """Détecte les sauts de position irréalistes"""
        try:
            # Calculer la distance
            distance = self._calculate_distance(
                float(current_data.get('latitude')),
                float(current_data.get('longitude')),
                float(last_position.latitude),
                float(last_position.longitude)
            )

            # Calculer le temps écoulé
            time_diff = (timezone.now() - last_position.timestamp).total_seconds()

            # Vitesse maximale théorique
            max_theoretical_speed = 100  # km/h

            # Convertir en mètres par seconde
            max_distance = (max_theoretical_speed * 1000 / 3600) * time_diff

            return distance > max_distance

        except Exception as e:
            self.log_error(f"Error detecting position jump: {str(e)}", exc=e)
            return False

    def _check_route_deviation(self, data, trip):
        """Calcule la déviation par rapport à l'itinéraire"""
        try:
            route = trip.route
            lat = float(data.get('latitude'))
            lon = float(data.get('longitude'))

            # Trouver les segments de route les plus proches
            nearest_segment = self._find_nearest_route_segment(lat, lon, route)
            if not nearest_segment:
                return float('inf')

            # Calculer la distance minimale au segment
            return self._calculate_distance_to_segment(lat, lon, nearest_segment)

        except Exception as e:
            self.log_error(f"Error checking route deviation: {str(e)}", exc=e)
            return float('inf')

    def _is_at_stop(self, data, trip):
        """Vérifie si la position est à un arrêt"""
        try:
            lat = float(data.get('latitude'))
            lon = float(data.get('longitude'))
            speed = float(data.get('speed', 0))

            if speed > 5:  # km/h
                return False

            # Trouver l'arrêt le plus proche
            nearest_stop = Stop.objects.filter(
                route=trip.route
            ).annotate(
                distance=self._calculate_distance_expression(lat, lon)
            ).filter(
                distance__lte=self.STOP_RADIUS
            ).order_by('distance').first()

            return bool(nearest_stop)

        except Exception as e:
            self.log_error(f"Error checking stop position: {str(e)}", exc=e)
            return False

    def _validate_stop_rules(self, data, trip, results):
        """Valide les règles spécifiques aux arrêts"""
        try:
            # Vérifier la durée d'arrêt
            stop_duration = self._calculate_stop_duration(trip)
            
            if stop_duration > self.MAX_STOP_DURATION:
                results['warnings'].append(f'Stop duration exceeded: {stop_duration}s')
            elif stop_duration < self.MIN_STOP_DURATION:
                results['warnings'].append('Stop duration too short')

            # Vérifier le respect des horaires
            scheduled_time = self._get_scheduled_stop_time(trip)
            if scheduled_time:
                time_diff = (timezone.now() - scheduled_time).total_seconds()
                if abs(time_diff) > 300:  # 5 minutes
                    results['warnings'].append('Stop time deviation detected')

        except Exception as e:
            self.log_error(f"Error validating stop rules: {str(e)}", exc=e)

    def _validate_contextual_speed(self, data, trip, results):
        """Valide la vitesse en fonction du contexte"""
        try:
            speed = float(data.get('speed', 0))
            
            # 1. Vérifier les limites de vitesse de la zone
            zone_speed_limit = self._get_zone_speed_limit(data, trip)
            if speed > zone_speed_limit:
                results['warnings'].append(f'Speed limit exceeded: {speed} km/h in {zone_speed_limit} km/h zone')

            # 2. Vérifier la vitesse appropriée pour les virages
            if self._is_in_curve(data, trip) and speed > 30:
                results['warnings'].append('Speed too high for curve')

            # 3. Vérifier la vitesse à l'approche des arrêts
            if self._is_approaching_stop(data, trip) and speed > 20:
                results['warnings'].append('Speed too high approaching stop')

        except Exception as e:
            self.log_error(f"Error validating contextual speed: {str(e)}", exc=e)

    def _get_zone_speed_limit(self, data, trip):
        """Obtient la limite de vitesse de la zone"""
        # À implémenter selon vos besoins
        return 50  # km/h par défaut

    def _is_in_curve(self, data, trip):
        """Détermine si le véhicule est dans un virage"""
        # À implémenter selon vos besoins
        return False

    def _is_approaching_stop(self, data, trip):
        """Détermine si le véhicule approche d'un arrêt"""
        try:
            lat = float(data.get('latitude'))
            lon = float(data.get('longitude'))

            # Trouver l'arrêt le plus proche
            next_stop = Stop.objects.filter(
                route=trip.route
            ).annotate(
                distance=self._calculate_distance_expression(lat, lon)
            ).filter(
                distance__lte=100  # 100 mètres
            ).first()

            return bool(next_stop)

        except Exception as e:
            self.log_error(f"Error checking stop approach: {str(e)}", exc=e)
            return False

    def log_validation_result(self, position_data, validation_results):
        """Enregistre les résultats de la validation"""
        try:
            if not validation_results['is_valid'] or validation_results['warnings']:
                EventLog.objects.create(
                    trip_id=position_data.get('trip_id'),
                    event_type='validation_result',
                    description='Position validation results',
                    details={
                        'position': {
                            'lat': position_data.get('latitude'),
                            'lon': position_data.get('longitude'),
                            'speed': position_data.get('speed')
                        },
                        'validation_results': validation_results
                    }
                )
        except Exception as e:
            self.log_error(f"Error logging validation result: {str(e)}", exc=e)