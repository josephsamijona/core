# transport_management/services/monitoring/trip_monitor.py

from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Avg, F, Q
from ...models import Trip, BusPosition, Stop, Schedule, EventLog
from ..base.service_base import ServiceBase

class TripMonitoringService(ServiceBase):
    def __init__(self):
        super().__init__()
        self.DELAY_THRESHOLD = 5  # minutes
        self.WARNING_THRESHOLD = 3  # minutes

    def monitor_active_trips(self):
        """
        Surveillance continue des trips actifs
        """
        try:
            active_trips = Trip.objects.filter(
                status='in_progress'
            ).select_related('schedule', 'route')

            for trip in active_trips:
                self._process_trip_monitoring(trip)

        except Exception as e:
            self.log_error(f"Error monitoring active trips: {str(e)}", exc=e)

    def _process_trip_monitoring(self, trip):
        """Traite la surveillance d'un trip spécifique"""
        try:
            # 1. Obtenir la dernière position
            latest_position = self._get_latest_position(trip)
            if not latest_position:
                return

            # 2. Calculer les écarts par rapport au schedule
            schedule_deviation = self._calculate_schedule_deviation(trip, latest_position)

            # 3. Mettre à jour les estimations
            self._update_predictions(trip, latest_position, schedule_deviation)

            # 4. Gérer les retards si nécessaire
            if schedule_deviation.get('is_delayed', False):
                self._handle_delay(trip, schedule_deviation)

        except Exception as e:
            self.log_error(f"Error processing trip monitoring for trip {trip.id}: {str(e)}", exc=e)

    def _get_latest_position(self, trip):
        """Récupère et valide la dernière position"""
        latest_position = BusPosition.objects.filter(
            trip=trip
        ).order_by('-timestamp').first()

        if not latest_position:
            self.log_warning(f"No position data found for trip {trip.id}")
            return None

        # Vérifier si la position n'est pas trop ancienne (> 5 minutes)
        if (timezone.now() - latest_position.timestamp) > timedelta(minutes=5):
            self.log_warning(f"Position data is stale for trip {trip.id}")
            return None

        return latest_position

    def _calculate_schedule_deviation(self, trip, position):
        """
        Calcule les écarts par rapport au schedule
        Retourne un dict avec les informations de déviation
        """
        try:
            # 1. Trouver le prochain arrêt prévu
            next_stop = self._get_next_scheduled_stop(trip, position)
            if not next_stop:
                return {'is_delayed': False}

            # 2. Calculer l'heure prévue pour cet arrêt
            scheduled_time = self._get_scheduled_time_for_stop(trip, next_stop)
            if not scheduled_time:
                return {'is_delayed': False}

            # 3. Calculer le temps estimé d'arrivée
            eta = self._calculate_eta_to_stop(position, next_stop)
            
            # 4. Calculer l'écart
            time_difference = (eta - scheduled_time).total_seconds() / 60

            return {
                'is_delayed': time_difference > self.DELAY_THRESHOLD,
                'delay_minutes': max(0, time_difference),
                'next_stop': next_stop,
                'scheduled_time': scheduled_time,
                'estimated_time': eta,
                'schedule_adherence': self._calculate_adherence_status(time_difference)
            }

        except Exception as e:
            self.log_error(f"Error calculating schedule deviation: {str(e)}", exc=e)
            return {'is_delayed': False}

    def _get_next_scheduled_stop(self, trip, position):
        """Détermine le prochain arrêt prévu"""
        try:
            # Obtenir tous les arrêts de la route
            route_stops = trip.route.stops.all()
            
            # Trouver l'arrêt le plus proche qui n'a pas encore été visité
            visited_stops = EventLog.objects.filter(
                trip=trip,
                event_type='stop_arrival'
            ).values_list('related_stop_id', flat=True)

            for stop in route_stops:
                if stop.id not in visited_stops:
                    return stop

            return None

        except Exception as e:
            self.log_error(f"Error getting next scheduled stop: {str(e)}", exc=e)
            return None

    def _get_scheduled_time_for_stop(self, trip, stop):
        """Obtient l'heure prévue pour un arrêt"""
        try:
            # Calculer le temps prévu basé sur l'horaire et la position de l'arrêt
            schedule = trip.schedule
            if not schedule:
                return None

            # Obtenir l'index de l'arrêt dans la route
            stop_index = list(trip.route.stops.all()).index(stop)
            
            # Calculer le temps prévu (simplification)
            minutes_per_stop = schedule.estimated_duration / trip.route.stops.count()
            scheduled_time = trip.planned_departure + timedelta(minutes=stop_index * minutes_per_stop)

            return scheduled_time

        except Exception as e:
            self.log_error(f"Error getting scheduled time for stop: {str(e)}", exc=e)
            return None

    def _calculate_eta_to_stop(self, position, stop):
        """Calcule l'heure estimée d'arrivée à un arrêt"""
        try:
            # 1. Calculer la distance jusqu'à l'arrêt
            distance = self._calculate_distance(
                position.latitude, position.longitude,
                stop.latitude, stop.longitude
            )

            # 2. Calculer la vitesse moyenne récente
            avg_speed = position.trip.busposition_set.filter(
                timestamp__gte=timezone.now() - timedelta(minutes=15),
                is_moving=True
            ).aggregate(Avg('speed'))['speed__avg'] or position.speed

            if avg_speed <= 0:
                avg_speed = 20  # vitesse par défaut en km/h

            # 3. Calculer le temps estimé
            hours = distance / avg_speed
            return timezone.now() + timedelta(hours=hours)

        except Exception as e:
            self.log_error(f"Error calculating ETA: {str(e)}", exc=e)
            return timezone.now()

    def _calculate_adherence_status(self, time_difference):
        """Détermine le statut d'adhérence au schedule"""
        if time_difference <= self.WARNING_THRESHOLD:
            return 'on_time'
        elif time_difference <= self.DELAY_THRESHOLD:
            return 'slight_delay'
        else:
            return 'delayed'

    def _update_predictions(self, trip, position, deviation):
        """Met à jour les prédictions pour le reste du trajet"""
        try:
            if not deviation['is_delayed']:
                return

            # 1. Calculer le retard actuel
            current_delay = deviation['delay_minutes']

            # 2. Ajuster les estimations pour les arrêts restants
            remaining_stops = trip.route.stops.filter(
                id__gt=deviation['next_stop'].id
            )

            # 3. Propager le retard (avec possibilité de rattrapage)
            recovery_rate = self._calculate_recovery_rate(trip)
            
            for stop in remaining_stops:
                delay_at_stop = max(0, current_delay - (recovery_rate * stop.sequence))
                # Stocker les prédictions
                self._store_stop_prediction(trip, stop, delay_at_stop)

        except Exception as e:
            self.log_error(f"Error updating predictions: {str(e)}", exc=e)

    def _calculate_recovery_rate(self, trip):
        """Calcule le taux de rattrapage possible du retard"""
        # Logique simplifiée - à adapter selon vos besoins
        return 0.5  # minutes par arrêt

    def _store_stop_prediction(self, trip, stop, delay):
        """Stocke les prédictions pour un arrêt"""
        try:
            with transaction.atomic():
                # Mettre à jour ou créer une prédiction
                prediction, created = trip.predictions.get_or_create(
                    stop=stop,
                    defaults={
                        'predicted_delay': delay,
                        'confidence_level': self._calculate_confidence(delay)
                    }
                )
                
                if not created:
                    prediction.predicted_delay = delay
                    prediction.confidence_level = self._calculate_confidence(delay)
                    prediction.save()

        except Exception as e:
            self.log_error(f"Error storing stop prediction: {str(e)}", exc=e)

    def _calculate_confidence(self, delay):
        """Calcule le niveau de confiance de la prédiction"""
        # Logique simplifiée - à adapter selon vos besoins
        if delay < 5:
            return 'high'
        elif delay < 15:
            return 'medium'
        else:
            return 'low'

    def _handle_delay(self, trip, deviation):
        """Gère un retard détecté"""
        try:
            # 1. Mettre à jour le statut du trip
            trip.delay_minutes = deviation['delay_minutes']
            trip.status = 'delayed'
            trip.save()

            # 2. Créer un événement de retard
            if not EventLog.objects.filter(
                trip=trip,
                event_type='delay',
                timestamp__gte=timezone.now() - timedelta(minutes=15)
            ).exists():
                EventLog.objects.create(
                    trip=trip,
                    event_type='delay',
                    description=f"Delay of {deviation['delay_minutes']} minutes detected",
                    timestamp=timezone.now()
                )

            # 3. Si le retard est important, déclencher des notifications
            if deviation['delay_minutes'] > self.DELAY_THRESHOLD * 2:
                self._trigger_delay_notifications(trip, deviation)

        except Exception as e:
            self.log_error(f"Error handling delay: {str(e)}", exc=e)

    def _trigger_delay_notifications(self, trip, deviation):
        """Déclenche les notifications de retard"""
        # À implémenter selon vos besoins de notification
        pass