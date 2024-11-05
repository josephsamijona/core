# transport_management/services/tracking/position_tracking.py

# transport_management/services/tracking/position_tracking.py

from django.db import transaction
from django.utils import timezone
from django.db.models import Avg  # Ajout de l'import
from datetime import datetime, timedelta
import json
from math import radians, sin, cos, sqrt, atan2
from ...models import Trip, BusPosition, Stop
from ..base.service_base import ServiceBase

class PositionTrackingService(ServiceBase):
    def __init__(self):
        super().__init__()

    def process_gps_data(self, raw_data):
        """
        Traite les données GPS reçues du mobile
        Format attendu:
        {
            "trip_id": "123",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "altitude": 35.6,
            "speed": 30.5,
            "heading": 180.0,
            "accuracy": 10.0,
            "timestamp": "2024-01-01T12:00:00Z"
        }
        """
        try:
            # Validation des données
            validated_data = self._validate_gps_data(raw_data)
            if not validated_data:
                return False

            # Création de la position
            position = self._create_position(validated_data)
            
            # Mise à jour des métriques et détection des événements
            self._update_trip_metrics(position)
            
            return position

        except Exception as e:
            self.log_error(f"Error processing GPS data: {str(e)}", exc=e)
            return None

    def _validate_gps_data(self, data):
        """Valide les données GPS reçues"""
        required_fields = ['trip_id', 'latitude', 'longitude', 'timestamp']
        
        try:
            # Vérification des champs requis
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            # Validation du trip
            trip = Trip.objects.get(id=data['trip_id'])
            if trip.status not in ['in_progress', 'planned']:
                raise ValueError(f"Invalid trip status: {trip.status}")

            # Validation des coordonnées
            lat = float(data['latitude'])
            lon = float(data['longitude'])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Invalid coordinates")

            return {
                'trip': trip,
                'latitude': lat,
                'longitude': lon,
                'altitude': float(data.get('altitude', 0)),
                'speed': float(data.get('speed', 0)),
                'heading': float(data.get('heading', 0)),
                'accuracy': float(data.get('accuracy', 0)),
                'timestamp': datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            }

        except Exception as e:
            self.log_error(f"Data validation error: {str(e)}", exc=e)
            return None

    def _create_position(self, validated_data):
        """Crée une nouvelle position avec les données validées"""
        try:
            with transaction.atomic():
                # Récupérer la dernière position
                last_position = BusPosition.objects.filter(
                    trip=validated_data['trip']
                ).order_by('-timestamp').first()

                # Calculer si le bus est en mouvement
                is_moving = self._calculate_is_moving(
                    validated_data['speed'],
                    last_position
                )

                # Créer la nouvelle position
                position = BusPosition.objects.create(
                    trip=validated_data['trip'],
                    latitude=validated_data['latitude'],
                    longitude=validated_data['longitude'],
                    altitude=validated_data['altitude'],
                    speed=validated_data['speed'],
                    heading=validated_data['heading'],
                    accuracy=validated_data['accuracy'],
                    timestamp=validated_data['timestamp'],
                    is_moving=is_moving,
                    position_status='active',
                    data_source='mobile_android'
                )

                return position

        except Exception as e:
            self.log_error(f"Error creating position: {str(e)}", exc=e)
            raise

    def _calculate_is_moving(self, current_speed, last_position=None):
        """Détermine si le bus est en mouvement"""
        SPEED_THRESHOLD = 3.0  # km/h
        
        if current_speed > SPEED_THRESHOLD:
            return True
            
        if last_position and (timezone.now() - last_position.timestamp).seconds < 60:
            distance = self._calculate_distance(
                last_position.latitude, last_position.longitude,
                float(current_speed), float(last_position.longitude)
            )
            return distance > 0.01  # 10 mètres

        return False

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calcule la distance entre deux points GPS en kilomètres"""
        R = 6371  # Rayon de la Terre en km

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c

    def _update_trip_metrics(self, position):
        """Met à jour les métriques du trip et détecte les événements"""
        try:
            trip = position.trip
            
            # 1. Vérification de la conformité à l'itinéraire
            route_conformity = self._check_route_conformity(position)
            
            # 2. Détection des arrêts
            if not position.is_moving:
                self._detect_stop(position)
            
            # 3. Mise à jour des estimations
            self._update_arrival_estimates(trip, position)

        except Exception as e:
            self.log_error(f"Error updating trip metrics: {str(e)}", exc=e)

    def _check_route_conformity(self, position):
        """Vérifie si le bus suit bien l'itinéraire prévu"""
        try:
            route = position.trip.route
            max_deviation = 0.100  # 100 mètres de déviation maximum

            # Vérifier la distance par rapport au trajet prévu
            # Logique simplifiée pour l'exemple
            is_conforming = True  # À implémenter selon vos besoins
            
            if not is_conforming:
                self._log_route_deviation(position)

            return is_conforming

        except Exception as e:
            self.log_error(f"Error checking route conformity: {str(e)}", exc=e)
            return False

    def _detect_stop(self, position):
        """Détecte si le bus est à un arrêt"""
        try:
            STOP_RADIUS = 0.050  # 50 mètres
            
            # Trouver les arrêts à proximité
            nearby_stops = Stop.objects.filter(
                route=position.trip.route
            ).extra(
                select={'distance': 'ST_Distance_Sphere(location, Point(%s, %s))'},
                select_params=[position.longitude, position.latitude]
            ).filter(distance__lte=STOP_RADIUS)

            if nearby_stops.exists():
                self._log_stop_arrival(position, nearby_stops.first())

        except Exception as e:
            self.log_error(f"Error detecting stop: {str(e)}", exc=e)

    def _update_arrival_estimates(self, trip, position):
        """Met à jour les estimations d'arrivée"""
        try:
            # Calculer le temps restant estimé
            remaining_distance = self._calculate_remaining_distance(position)
            average_speed = self._calculate_average_speed(trip)
            
            if average_speed > 0:
                estimated_time = remaining_distance / average_speed
                new_eta = timezone.now() + timedelta(hours=estimated_time)
                
                trip.estimated_arrival = new_eta
                trip.save()

        except Exception as e:
            self.log_error(f"Error updating arrival estimates: {str(e)}", exc=e)

    def _calculate_remaining_distance(self, position):
        """Calcule la distance restante jusqu'à la destination"""
        # À implémenter selon vos besoins
        return 0

    def _calculate_average_speed(self, trip):
        """Calcule la vitesse moyenne du trip"""
        return BusPosition.objects.filter(
            trip=trip,
            is_moving=True,
            timestamp__gte=timezone.now() - timedelta(minutes=30)
        ).aggregate(Avg('speed'))['speed__avg'] or 0