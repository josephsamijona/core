# transport_management/services/reporting/reporting_service.py

from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Avg, Count, Sum, F, Q, ExpressionWrapper, fields
from ...models import Trip, BusPosition, EventLog, Stop, Route
from ..base.service_base import ServiceBase

class ReportingService(ServiceBase):
    def __init__(self):
        super().__init__()
        self.PUNCTUALITY_THRESHOLD = 300  # 5 minutes
        self.ROUTE_CONFORMITY_THRESHOLD = 100  # 100 mètres

    def generate_trip_analysis(self, trip_id=None, date_from=None, date_to=None):
        """Génère une analyse complète des trajets"""
        try:
            # Préparer la requête
            if trip_id:
                trips = Trip.objects.filter(id=trip_id)
            else:
                trips = Trip.objects.filter(
                    created_at__range=(date_from or timezone.now().date(), 
                                     date_to or timezone.now().date())
                )

            analysis = {
                'punctuality': self._analyze_punctuality(trips),
                'route_conformity': self._analyze_route_conformity(trips),
                'service_quality': self._analyze_service_quality(trips),
                'position_history': self._analyze_position_history(trips),
                'summary': self._generate_summary(trips),
                'generated_at': timezone.now().isoformat()
            }

            return analysis

        except Exception as e:
            self.log_error(f"Error generating trip analysis: {str(e)}", exc=e)
            return None

    def _analyze_punctuality(self, trips):
        """Analyse la ponctualité des trajets"""
        try:
            punctuality_stats = {
                'on_time': 0,
                'slightly_late': 0,
                'late': 0,
                'very_late': 0,
                'details': []
            }

            for trip in trips:
                delay = self._calculate_trip_delay(trip)
                stats = self._classify_delay(delay)
                punctuality_stats[stats['category']] += 1

                punctuality_stats['details'].append({
                    'trip_id': trip.id,
                    'planned_departure': trip.planned_departure.isoformat(),
                    'actual_departure': trip.actual_start_time.isoformat() if trip.actual_start_time else None,
                    'delay_minutes': delay // 60,
                    'status': stats['category'],
                    'stops_punctuality': self._analyze_stop_punctuality(trip)
                })

            total_trips = len(trips)
            if total_trips > 0:
                punctuality_stats['percentages'] = {
                    'on_time': (punctuality_stats['on_time'] / total_trips) * 100,
                    'slightly_late': (punctuality_stats['slightly_late'] / total_trips) * 100,
                    'late': (punctuality_stats['late'] / total_trips) * 100,
                    'very_late': (punctuality_stats['very_late'] / total_trips) * 100
                }

            return punctuality_stats

        except Exception as e:
            self.log_error(f"Error analyzing punctuality: {str(e)}", exc=e)
            return None

    def _analyze_route_conformity(self, trips):
        """Analyse la conformité à l'itinéraire"""
        try:
            conformity_stats = {
                'compliant': 0,
                'minor_deviations': 0,
                'major_deviations': 0,
                'details': []
            }

            for trip in trips:
                deviations = self._calculate_route_deviations(trip)
                stats = self._classify_deviations(deviations)
                conformity_stats[stats['category']] += 1

                conformity_stats['details'].append({
                    'trip_id': trip.id,
                    'total_deviations': len(deviations),
                    'max_deviation': stats['max_deviation'],
                    'avg_deviation': stats['avg_deviation'],
                    'status': stats['category'],
                    'deviation_points': deviations
                })

            return conformity_stats

        except Exception as e:
            self.log_error(f"Error analyzing route conformity: {str(e)}", exc=e)
            return None

    def _analyze_service_quality(self, trips):
        """Analyse la qualité du service"""
        try:
            quality_stats = {
                'completed_trips': 0,
                'cancelled_trips': 0,
                'interrupted_trips': 0,
                'incidents': 0,
                'avg_speed': 0,
                'stop_accuracy': 0,
                'details': []
            }

            for trip in trips:
                stats = self._calculate_service_metrics(trip)
                quality_stats['completed_trips'] += 1 if trip.status == 'completed' else 0
                quality_stats['cancelled_trips'] += 1 if trip.status == 'cancelled' else 0
                quality_stats['interrupted_trips'] += 1 if trip.status == 'interrupted' else 0
                quality_stats['incidents'] += stats['incident_count']
                
                quality_stats['details'].append({
                    'trip_id': trip.id,
                    'status': trip.status,
                    'incident_count': stats['incident_count'],
                    'avg_speed': stats['avg_speed'],
                    'stop_accuracy': stats['stop_accuracy'],
                    'service_metrics': stats['metrics']
                })

            total_trips = len(trips)
            if total_trips > 0:
                quality_stats['completion_rate'] = (quality_stats['completed_trips'] / total_trips) * 100
                quality_stats['cancellation_rate'] = (quality_stats['cancelled_trips'] / total_trips) * 100
                quality_stats['interruption_rate'] = (quality_stats['interrupted_trips'] / total_trips) * 100

            return quality_stats

        except Exception as e:
            self.log_error(f"Error analyzing service quality: {str(e)}", exc=e)
            return None

    def _analyze_position_history(self, trips):
        """Analyse l'historique des positions"""
        try:
            position_stats = {
                'total_positions': 0,
                'valid_positions': 0,
                'invalid_positions': 0,
                'tracking_gaps': 0,
                'details': []
            }

            for trip in trips:
                stats = self._analyze_trip_positions(trip)
                position_stats['total_positions'] += stats['total_positions']
                position_stats['valid_positions'] += stats['valid_positions']
                position_stats['invalid_positions'] += stats['invalid_positions']
                position_stats['tracking_gaps'] += stats['tracking_gaps']

                position_stats['details'].append({
                    'trip_id': trip.id,
                    'position_count': stats['total_positions'],
                    'tracking_quality': stats['tracking_quality'],
                    'gaps': stats['gap_details'],
                    'coverage': stats['coverage_percentage']
                })

            return position_stats

        except Exception as e:
            self.log_error(f"Error analyzing position history: {str(e)}", exc=e)
            return None

    def _calculate_trip_delay(self, trip):
        """Calcule le retard d'un trip en secondes"""
        try:
            if not trip.actual_start_time:
                return 0

            delay = (trip.actual_start_time - trip.planned_departure).total_seconds()
            return max(0, delay)

        except Exception as e:
            self.log_error(f"Error calculating trip delay: {str(e)}", exc=e)
            return 0

    def _classify_delay(self, delay_seconds):
        """Classifie le retard"""
        if delay_seconds <= self.PUNCTUALITY_THRESHOLD:
            return {'category': 'on_time', 'description': 'À l\'heure'}
        elif delay_seconds <= self.PUNCTUALITY_THRESHOLD * 2:
            return {'category': 'slightly_late', 'description': 'Légèrement en retard'}
        elif delay_seconds <= self.PUNCTUALITY_THRESHOLD * 4:
            return {'category': 'late', 'description': 'En retard'}
        else:
            return {'category': 'very_late', 'description': 'Très en retard'}

    def _analyze_stop_punctuality(self, trip):
        """Analyse la ponctualité aux arrêts"""
        try:
            stop_events = EventLog.objects.filter(
                trip=trip,
                event_type='stop_arrival'
            ).order_by('timestamp')

            stop_stats = []
            for event in stop_events:
                scheduled_time = self._get_scheduled_stop_time(trip, event.stop)
                if scheduled_time:
                    delay = (event.timestamp - scheduled_time).total_seconds()
                    stop_stats.append({
                        'stop_id': event.stop.id,
                        'stop_name': event.stop.name,
                        'scheduled_time': scheduled_time.isoformat(),
                        'actual_time': event.timestamp.isoformat(),
                        'delay_seconds': delay,
                        'status': self._classify_delay(delay)['category']
                    })

            return stop_stats

        except Exception as e:
            self.log_error(f"Error analyzing stop punctuality: {str(e)}", exc=e)
            return []

    def _calculate_route_deviations(self, trip):
        """Calcule les déviations de l'itinéraire"""
        try:
            positions = BusPosition.objects.filter(
                trip=trip,
                is_valid=True
            ).order_by('timestamp')

            deviations = []
            for pos in positions:
                deviation = self._calculate_position_deviation(pos, trip.route)
                if deviation > self.ROUTE_CONFORMITY_THRESHOLD:
                    deviations.append({
                        'timestamp': pos.timestamp.isoformat(),
                        'position': {
                            'lat': pos.latitude,
                            'lon': pos.longitude
                        },
                        'deviation_meters': deviation
                    })

            return deviations

        except Exception as e:
            self.log_error(f"Error calculating route deviations: {str(e)}", exc=e)
            return []

    def _analyze_trip_positions(self, trip):
        """Analyse les positions d'un trip"""
        try:
            positions = BusPosition.objects.filter(
                trip=trip
            ).order_by('timestamp')

            stats = {
                'total_positions': positions.count(),
                'valid_positions': positions.filter(is_valid=True).count(),
                'invalid_positions': positions.filter(is_valid=False).count(),
                'tracking_gaps': 0,
                'gap_details': [],
                'tracking_quality': 'good',
                'coverage_percentage': 0
            }

            # Détecter les trous dans le tracking
            last_timestamp = None
            for pos in positions:
                if last_timestamp:
                    gap = (pos.timestamp - last_timestamp).total_seconds()
                    if gap > 60:  # Trou de plus d'une minute
                        stats['tracking_gaps'] += 1
                        stats['gap_details'].append({
                            'start': last_timestamp.isoformat(),
                            'end': pos.timestamp.isoformat(),
                            'duration_seconds': gap
                        })
                last_timestamp = pos.timestamp

            # Calculer le pourcentage de couverture
            if trip.actual_end_time and trip.actual_start_time:
                expected_positions = (trip.actual_end_time - trip.actual_start_time).total_seconds() / 30
                stats['coverage_percentage'] = (stats['valid_positions'] / expected_positions) * 100

            # Évaluer la qualité du tracking
            if stats['coverage_percentage'] >= 90:
                stats['tracking_quality'] = 'excellent'
            elif stats['coverage_percentage'] >= 75:
                stats['tracking_quality'] = 'good'
            elif stats['coverage_percentage'] >= 50:
                stats['tracking_quality'] = 'fair'
            else:
                stats['tracking_quality'] = 'poor'

            return stats

        except Exception as e:
            self.log_error(f"Error analyzing trip positions: {str(e)}", exc=e)
            return {
                'total_positions': 0,
                'valid_positions': 0,
                'invalid_positions': 0,
                'tracking_gaps': 0,
                'gap_details': [],
                'tracking_quality': 'unknown',
                'coverage_percentage': 0
            }

    def _generate_summary(self, trips):
        """Génère un résumé des analyses"""
        try:
            total_trips = len(trips)
            completed_trips = sum(1 for trip in trips if trip.status == 'completed')
            
            return {
                'total_trips': total_trips,
                'completion_rate': (completed_trips / total_trips * 100) if total_trips > 0 else 0,
                'average_delay': self._calculate_average_delay(trips),
                'route_conformity_rate': self._calculate_conformity_rate(trips),
                'tracking_quality': self._calculate_overall_tracking_quality(trips),
                'period': {
                    'start': trips.order_by('created_at').first().created_at.isoformat() if trips else None,
                    'end': trips.order_by('-created_at').first().created_at.isoformat() if trips else None
                }
            }

        except Exception as e:
            self.log_error(f"Error generating summary: {str(e)}", exc=e)
            return {}