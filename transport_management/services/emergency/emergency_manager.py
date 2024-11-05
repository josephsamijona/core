# transport_management/services/emergency/emergency_manager.py

from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q, Avg, Count
from ...models import Trip, BusPosition, EventLog, Incident, Stop
from ..base.service_base import ServiceBase

class EmergencyManager(ServiceBase):
    def __init__(self):
        super().__init__()
        # Seuils de détection
        self.UNPLANNED_STOP_THRESHOLD = 300  # secondes (5 minutes)
        self.MAJOR_DEVIATION_THRESHOLD = 200  # mètres
        self.SPEED_ANOMALY_THRESHOLD = 20  # km/h au-dessus de la moyenne
        self.SUDDEN_STOP_THRESHOLD = 30  # km/h/s (décélération brutale)
        self.EMERGENCY_CHECK_INTERVAL = 60  # secondes

        # Niveaux de gravité
        self.SEVERITY_LEVELS = {
            'low': 1,
            'medium': 2,
            'high': 3,
            'critical': 4
        }

    def check_emergencies(self, trip_id=None):
        """Vérifie les situations d'urgence"""
        try:
            if trip_id:
                trips = Trip.objects.filter(id=trip_id)
            else:
                trips = Trip.objects.filter(status__in=['in_progress', 'delayed'])

            for trip in trips:
                self._process_emergency_checks(trip)

        except Exception as e:
            self.log_error(f"Error checking emergencies: {str(e)}", exc=e)

    def _process_emergency_checks(self, trip):
        """Traite les vérifications d'urgence pour un trip"""
        try:
            latest_position = self._get_latest_position(trip)
            if not latest_position:
                return

            emergency_situations = []

            # 1. Vérifier les arrêts non prévus
            unplanned_stop = self._check_unplanned_stop(trip, latest_position)
            if unplanned_stop:
                emergency_situations.append(unplanned_stop)

            # 2. Vérifier les déviations
            deviation = self._check_major_deviation(trip, latest_position)
            if deviation:
                emergency_situations.append(deviation)

            # 3. Vérifier les anomalies de vitesse
            speed_anomaly = self._check_speed_anomaly(trip, latest_position)
            if speed_anomaly:
                emergency_situations.append(speed_anomaly)

            # 4. Gérer les situations d'urgence détectées
            if emergency_situations:
                self._handle_emergencies(trip, emergency_situations)

        except Exception as e:
            self.log_error(f"Error processing emergency checks for trip {trip.id}: {str(e)}", exc=e)

    def _check_unplanned_stop(self, trip, position):
        """Détecte les arrêts non prévus"""
        try:
            if position.speed > 5:  # km/h
                return None

            # Vérifier si le véhicule est arrêté depuis un moment
            stop_duration = self._calculate_stop_duration(trip, position)
            if stop_duration < self.UNPLANNED_STOP_THRESHOLD:
                return None

            # Vérifier si l'arrêt est prévu
            if self._is_at_scheduled_stop(trip, position):
                return None

            severity = self._calculate_stop_severity(stop_duration)
            
            return {
                'type': 'unplanned_stop',
                'severity': severity,
                'details': {
                    'duration': stop_duration,
                    'location': {
                        'lat': position.latitude,
                        'lon': position.longitude
                    },
                    'timestamp': position.timestamp.isoformat()
                }
            }

        except Exception as e:
            self.log_error(f"Error checking unplanned stop: {str(e)}", exc=e)
            return None

    def _check_major_deviation(self, trip, position):
        """Détecte les déviations importantes"""
        try:
            deviation = self._calculate_route_deviation(trip, position)
            if deviation < self.MAJOR_DEVIATION_THRESHOLD:
                return None

            # Vérifier si la déviation est déjà connue
            if self._is_known_deviation(trip, position):
                return None

            severity = self._calculate_deviation_severity(deviation)

            return {
                'type': 'major_deviation',
                'severity': severity,
                'details': {
                    'deviation_distance': deviation,
                    'location': {
                        'lat': position.latitude,
                        'lon': position.longitude
                    },
                    'timestamp': position.timestamp.isoformat()
                }
            }

        except Exception as e:
            self.log_error(f"Error checking major deviation: {str(e)}", exc=e)
            return None

    def _check_speed_anomaly(self, trip, position):
        """Détecte les anomalies de vitesse"""
        try:
            # 1. Vérifier la vitesse excessive
            if self._check_excessive_speed(trip, position):
                return {
                    'type': 'excessive_speed',
                    'severity': 'high',
                    'details': {
                        'speed': position.speed,
                        'location': {
                            'lat': position.latitude,
                            'lon': position.longitude
                        },
                        'timestamp': position.timestamp.isoformat()
                    }
                }

            # 2. Vérifier les arrêts brusques
            sudden_stop = self._check_sudden_stop(trip, position)
            if sudden_stop:
                return {
                    'type': 'sudden_stop',
                    'severity': 'critical',
                    'details': sudden_stop
                }

            return None

        except Exception as e:
            self.log_error(f"Error checking speed anomaly: {str(e)}", exc=e)
            return None

    def _handle_emergencies(self, trip, emergencies):
        """Gère les situations d'urgence détectées"""
        try:
            with transaction.atomic():
                highest_severity = max(e['severity'] for e in emergencies)
                
                # Créer un incident pour chaque urgence
                for emergency in emergencies:
                    incident = self._create_emergency_incident(trip, emergency)
                    
                    # Enregistrer l'événement
                    self._log_emergency_event(trip, emergency)
                    
                    # Notifier les parties concernées
                    self._send_emergency_notifications(trip, emergency)

                # Mettre à jour le statut du trip si nécessaire
                if highest_severity in ['high', 'critical']:
                    trip.status = 'interrupted'
                    trip.save()

        except Exception as e:
            self.log_error(f"Error handling emergencies: {str(e)}", exc=e)

    def _create_emergency_incident(self, trip, emergency):
        """Crée un incident d'urgence"""
        try:
            return Incident.objects.create(
                trip=trip,
                type=emergency['type'],
                severity=emergency['severity'],
                description=self._generate_emergency_description(emergency),
                date=timezone.now(),
                status='reported',
                location=emergency['details'].get('location', {}),
                detailed_report=emergency['details']
            )
        except Exception as e:
            self.log_error(f"Error creating emergency incident: {str(e)}", exc=e)
            return None

    def _calculate_stop_duration(self, trip, position):
        """Calcule la durée d'un arrêt"""
        try:
            stop_positions = BusPosition.objects.filter(
                trip=trip,
                speed__lte=5,
                timestamp__lte=position.timestamp,
                timestamp__gte=position.timestamp - timedelta(minutes=10)
            ).order_by('timestamp')

            if not stop_positions:
                return 0

            first_stop = stop_positions.first()
            return (position.timestamp - first_stop.timestamp).total_seconds()

        except Exception as e:
            self.log_error(f"Error calculating stop duration: {str(e)}", exc=e)
            return 0

    def _is_at_scheduled_stop(self, trip, position):
        """Vérifie si la position est à un arrêt prévu"""
        try:
            return Stop.objects.filter(
                route=trip.route
            ).extra(
                select={'distance': 'ST_Distance_Sphere(location, Point(%s, %s))'},
                select_params=[position.longitude, position.latitude]
            ).filter(distance__lte=50).exists()

        except Exception as e:
            self.log_error(f"Error checking scheduled stop: {str(e)}", exc=e)
            return False

    def _check_excessive_speed(self, trip, position):
        """Vérifie si la vitesse est excessive"""
        try:
            # Calculer la vitesse moyenne récente
            avg_speed = BusPosition.objects.filter(
                trip=trip,
                timestamp__gte=timezone.now() - timedelta(minutes=5)
            ).aggregate(Avg('speed'))['speed__avg'] or 0

            return position.speed > (avg_speed + self.SPEED_ANOMALY_THRESHOLD)

        except Exception as e:
            self.log_error(f"Error checking excessive speed: {str(e)}", exc=e)
            return False

    def _check_sudden_stop(self, trip, position):
        """Vérifie s'il y a eu un arrêt brusque"""
        try:
            previous_position = BusPosition.objects.filter(
                trip=trip,
                timestamp__lt=position.timestamp
            ).order_by('-timestamp').first()

            if not previous_position:
                return None

            time_diff = (position.timestamp - previous_position.timestamp).total_seconds()
            if time_diff == 0:
                return None

            speed_change = previous_position.speed - position.speed
            deceleration = speed_change / time_diff

            if deceleration > self.SUDDEN_STOP_THRESHOLD:
                return {
                    'deceleration': deceleration,
                    'initial_speed': previous_position.speed,
                    'final_speed': position.speed,
                    'time_interval': time_diff
                }

            return None

        except Exception as e:
            self.log_error(f"Error checking sudden stop: {str(e)}", exc=e)
            return None

    def _send_emergency_notifications(self, trip, emergency):
        """Envoie les notifications d'urgence"""
        try:
            if emergency['severity'] in ['high', 'critical']:
                # Notification immédiate
                self._send_immediate_notification(trip, emergency)

            # Enregistrer dans les logs
            EventLog.objects.create(
                trip=trip,
                event_type='emergency_notification',
                description=f"Emergency {emergency['type']} detected",
                details=emergency['details']
            )

        except Exception as e:
            self.log_error(f"Error sending emergency notifications: {str(e)}", exc=e)

    def _generate_emergency_description(self, emergency):
        """Génère une description détaillée de l'urgence"""
        type_descriptions = {
            'unplanned_stop': 'Arrêt non planifié détecté',
            'major_deviation': 'Déviation majeure de l\'itinéraire',
            'excessive_speed': 'Vitesse excessive détectée',
            'sudden_stop': 'Arrêt brusque détecté'
        }

        base_description = type_descriptions.get(emergency['type'], 'Incident détecté')
        details = emergency['details']

        if emergency['type'] == 'unplanned_stop':
            return f"{base_description} - Durée: {details['duration']} secondes"
        elif emergency['type'] == 'major_deviation':
            return f"{base_description} - Distance: {details['deviation_distance']} mètres"
        elif emergency['type'] == 'excessive_speed':
            return f"{base_description} - Vitesse: {details['speed']} km/h"
        elif emergency['type'] == 'sudden_stop':
            return f"{base_description} - Décélération: {details['deceleration']:.1f} km/h/s"

        return base_description