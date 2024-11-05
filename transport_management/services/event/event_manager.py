# transport_management/services/event/event_manager.py

from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Avg, Q
from ...models import Trip, BusPosition, Stop, EventLog, Incident
from ..base.service_base import ServiceBase

class TripEventManager(ServiceBase):
    def __init__(self):
        super().__init__()
        # Seuils de configuration
        self.STOP_RADIUS = 50  # mètres
        self.STOP_DURATION = 30  # secondes
        self.DELAY_THRESHOLD = 300  # secondes (5 minutes)
        self.SPEED_THRESHOLD = 5  # km/h pour détecter un arrêt
        self.DEVIATION_THRESHOLD = 100  # mètres
        self.INCIDENT_SPEED_THRESHOLD = 3  # km/h pour détecter un incident potentiel

    def process_events(self, trip_id):
        """Traite les événements pour un trip donné"""
        try:
            trip = Trip.objects.get(id=trip_id)
            if trip.status not in ['in_progress', 'delayed']:
                return

            latest_position = self._get_latest_position(trip)
            if not latest_position:
                return

            # Détection parallèle des différents types d'événements
            self._detect_stop_events(trip, latest_position)
            self._detect_deviation_events(trip, latest_position)
            self._detect_delay_events(trip, latest_position)
            self._detect_incident_events(trip, latest_position)

        except Exception as e:
            self.log_error(f"Error processing events for trip {trip_id}: {str(e)}", exc=e)

    def _get_latest_position(self, trip):
        """Récupère la dernière position valide"""
        return BusPosition.objects.filter(
            trip=trip,
            is_valid=True
        ).order_by('-timestamp').first()

    def _detect_stop_events(self, trip, current_position):
        """Détecte les arrêts aux stations"""
        try:
            # Vérifier si le véhicule est arrêté
            if current_position.speed > self.SPEED_THRESHOLD:
                return

            # Vérifier la durée de l'arrêt
            previous_positions = BusPosition.objects.filter(
                trip=trip,
                timestamp__gte=current_position.timestamp - timedelta(seconds=self.STOP_DURATION),
                speed__lte=self.SPEED_THRESHOLD
            )

            if previous_positions.count() < 2:  # Pas assez de données pour confirmer un arrêt
                return

            # Trouver l'arrêt le plus proche
            nearby_stop = self._find_nearest_stop(trip, current_position)
            if not nearby_stop:
                return

            # Vérifier si cet arrêt n'a pas déjà été enregistré récemment
            recent_stop_event = EventLog.objects.filter(
                trip=trip,
                event_type='stop_arrival',
                related_stop=nearby_stop,
                timestamp__gte=timezone.now() - timedelta(minutes=5)
            ).exists()

            if not recent_stop_event:
                self._record_stop_event(trip, nearby_stop, current_position)

        except Exception as e:
            self.log_error(f"Error detecting stop events: {str(e)}", exc=e)

    def _detect_deviation_events(self, trip, current_position):
        """Détecte les déviations de l'itinéraire prévu"""
        try:
            # Calculer la déviation par rapport à l'itinéraire prévu
            deviation = self._calculate_route_deviation(trip, current_position)
            
            if deviation > self.DEVIATION_THRESHOLD:
                # Vérifier si une déviation similaire n'a pas déjà été signalée
                recent_deviation = EventLog.objects.filter(
                    trip=trip,
                    event_type='route_deviation',
                    timestamp__gte=timezone.now() - timedelta(minutes=2)
                ).exists()

                if not recent_deviation:
                    self._record_deviation_event(trip, current_position, deviation)

        except Exception as e:
            self.log_error(f"Error detecting deviation events: {str(e)}", exc=e)

    def _detect_delay_events(self, trip, current_position):
        """Détecte les retards"""
        try:
            # Calculer le retard actuel
            current_delay = self._calculate_current_delay(trip, current_position)
            
            if current_delay > self.DELAY_THRESHOLD:
                # Vérifier si ce retard n'a pas déjà été signalé
                recent_delay = EventLog.objects.filter(
                    trip=trip,
                    event_type='delay',
                    timestamp__gte=timezone.now() - timedelta(minutes=5)
                ).exists()

                if not recent_delay:
                    self._record_delay_event(trip, current_position, current_delay)

        except Exception as e:
            self.log_error(f"Error detecting delay events: {str(e)}", exc=e)

    def _detect_incident_events(self, trip, current_position):
        """Détecte les incidents potentiels"""
        try:
            # 1. Arrêt inattendu
            if self._detect_unexpected_stop(trip, current_position):
                self._record_incident_event(trip, 'unexpected_stop', current_position)

            # 2. Vitesse anormale
            if self._detect_abnormal_speed(trip, current_position):
                self._record_incident_event(trip, 'abnormal_speed', current_position)

            # 3. Mouvement irrégulier
            if self._detect_irregular_movement(trip, current_position):
                self._record_incident_event(trip, 'irregular_movement', current_position)

        except Exception as e:
            self.log_error(f"Error detecting incident events: {str(e)}", exc=e)

    def _find_nearest_stop(self, trip, position):
        """Trouve l'arrêt le plus proche"""
        return Stop.objects.filter(
            route=trip.route
        ).annotate(
            distance=self._calculate_distance_expression(position)
        ).filter(
            distance__lte=self.STOP_RADIUS
        ).order_by('distance').first()

    def _calculate_route_deviation(self, trip, position):
        """Calcule la déviation par rapport à l'itinéraire"""
        # Implémenter le calcul de déviation selon votre logique spécifique
        return 0

    def _calculate_current_delay(self, trip, position):
        """Calcule le retard actuel"""
        try:
            # Obtenir le prochain arrêt prévu
            next_stop = self._get_next_scheduled_stop(trip)
            if not next_stop:
                return 0

            # Calculer le temps prévu vs réel
            scheduled_time = self._get_scheduled_arrival_time(trip, next_stop)
            estimated_time = self._calculate_eta(position, next_stop)

            return (estimated_time - scheduled_time).total_seconds()

        except Exception as e:
            self.log_error(f"Error calculating delay: {str(e)}", exc=e)
            return 0

    def _detect_unexpected_stop(self, trip, position):
        """Détecte un arrêt inattendu"""
        if position.speed > self.INCIDENT_SPEED_THRESHOLD:
            return False

        # Vérifier si l'arrêt est près d'un arrêt prévu
        nearest_stop = self._find_nearest_stop(trip, position)
        if nearest_stop and self._calculate_distance(position, nearest_stop) <= self.STOP_RADIUS:
            return False

        # Vérifier la durée de l'arrêt
        stop_duration = self._calculate_stop_duration(trip, position)
        return stop_duration >= timedelta(minutes=2)

    def _detect_abnormal_speed(self, trip, position):
        """Détecte une vitesse anormale"""
        # Calculer la vitesse moyenne des 5 dernières minutes
        avg_speed = BusPosition.objects.filter(
            trip=trip,
            timestamp__gte=timezone.now() - timedelta(minutes=5)
        ).aggregate(Avg('speed'))['speed__avg'] or 0

        return abs(position.speed - avg_speed) > 20  # km/h

    def _detect_irregular_movement(self, trip, position):
        """Détecte un mouvement irrégulier"""
        recent_positions = BusPosition.objects.filter(
            trip=trip,
            timestamp__gte=timezone.now() - timedelta(minutes=1)
        ).order_by('timestamp')

        if recent_positions.count() < 3:
            return False

        # Analyser les changements brusques de direction
        prev_heading = None
        for pos in recent_positions:
            if prev_heading is not None:
                heading_change = abs(pos.heading - prev_heading)
                if heading_change > 45:  # Plus de 45 degrés en une minute
                    return True
            prev_heading = pos.heading

        return False

    def _record_event(self, trip, event_type, details, position):
        """Enregistre un événement"""
        try:
            with transaction.atomic():
                event = EventLog.objects.create(
                    trip=trip,
                    event_type=event_type,
                    description=details.get('description', ''),
                    timestamp=timezone.now(),
                    location_data={
                        'latitude': position.latitude,
                        'longitude': position.longitude
                    },
                    event_data=details
                )

                # Mettre à jour le statut du trip si nécessaire
                if event_type in ['incident', 'major_delay']:
                    self._update_trip_status(trip, event_type, details)

                return event

        except Exception as e:
            self.log_error(f"Error recording event: {str(e)}", exc=e)
            return None

    def _update_trip_status(self, trip, event_type, details):
        """Met à jour le statut du trip en fonction de l'événement"""
        status_mapping = {
            'incident': 'interrupted',
            'major_delay': 'delayed',
            'route_deviation': 'deviated'
        }

        if event_type in status_mapping:
            trip.status = status_mapping[event_type]
            trip.save()

    # Méthodes d'enregistrement spécifiques pour chaque type d'événement
    def _record_stop_event(self, trip, stop, position):
        self._record_event(trip, 'stop_arrival', {
            'description': f"Arrived at stop: {stop.name}",
            'stop_id': stop.id,
            'scheduled_time': self._get_scheduled_arrival_time(trip, stop)
        }, position)

    def _record_deviation_event(self, trip, position, deviation):
        self._record_event(trip, 'route_deviation', {
            'description': f"Route deviation of {deviation:.2f} meters",
            'deviation_distance': deviation
        }, position)

    def _record_delay_event(self, trip, position, delay):
        self._record_event(trip, 'delay', {
            'description': f"Delay of {delay/60:.1f} minutes detected",
            'delay_seconds': delay
        }, position)

    def _record_incident_event(self, trip, incident_type, position):
        self._record_event(trip, 'incident', {
            'description': f"Incident detected: {incident_type}",
            'incident_type': incident_type
        }, position)