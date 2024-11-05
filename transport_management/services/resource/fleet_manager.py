# transport_management/services/resource/fleet_manager.py

from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q, Count, Avg
from ...models import (
    Trip, DriverVehicleAssignment, BusPosition, 
    Driver, Schedule, ResourceAvailability
)
from ..base.service_base import ServiceBase

class FleetManager(ServiceBase):
    def __init__(self):
        super().__init__()
        self.ACTIVE_TIMEOUT = 300  # 5 minutes sans données = inactif

    def monitor_active_fleet(self):
        """Surveillance continue de la flotte active"""
        try:
            # 1. Mettre à jour les statuts
            self._update_fleet_status()
            
            # 2. Vérifier les assignations
            self._verify_assignments()
            
            # 3. Optimiser les attributions si nécessaire
            self._optimize_assignments()

        except Exception as e:
            self.log_error(f"Error monitoring fleet: {str(e)}", exc=e)

    def _update_fleet_status(self):
        """Mise à jour des statuts de la flotte"""
        try:
            current_time = timezone.now()
            timeout_threshold = current_time - timedelta(seconds=self.ACTIVE_TIMEOUT)

            # Récupérer toutes les assignations actives
            active_assignments = DriverVehicleAssignment.objects.filter(
                status='active',
                assigned_from__lte=current_time,
                assigned_until__gte=current_time
            ).select_related('vehicle', 'driver')

            for assignment in active_assignments:
                # Vérifier la dernière position connue
                last_position = BusPosition.objects.filter(
                    trip__vehicle=assignment.vehicle
                ).order_by('-timestamp').first()

                # Mettre à jour le statut basé sur l'activité récente
                if last_position and last_position.timestamp > timeout_threshold:
                    self._update_assignment_status(assignment, 'active', last_position)
                else:
                    self._update_assignment_status(assignment, 'inactive')

        except Exception as e:
            self.log_error(f"Error updating fleet status: {str(e)}", exc=e)

    def _verify_assignments(self):
        """Vérifie la validité des assignations actuelles"""
        try:
            current_time = timezone.now()
            
            # Vérifier les assignations qui se terminent bientôt
            ending_soon = DriverVehicleAssignment.objects.filter(
                status='active',
                assigned_until__lte=current_time + timedelta(hours=1)
            ).select_related('vehicle', 'driver')

            for assignment in ending_soon:
                self._handle_ending_assignment(assignment)

            # Vérifier les conflits d'assignation
            self._check_assignment_conflicts()

        except Exception as e:
            self.log_error(f"Error verifying assignments: {str(e)}", exc=e)

    def _optimize_assignments(self):
        """Optimise les attributions de véhicules"""
        try:
            # 1. Récupérer les besoins futurs
            upcoming_needs = self._get_upcoming_resource_needs()
            
            # 2. Évaluer la disponibilité
            available_assignments = self._get_available_assignments()
            
            # 3. Optimiser les attributions
            optimizations = self._calculate_optimizations(upcoming_needs, available_assignments)
            
            # 4. Appliquer les changements nécessaires
            self._apply_assignment_changes(optimizations)

        except Exception as e:
            self.log_error(f"Error optimizing assignments: {str(e)}", exc=e)

    def _update_assignment_status(self, assignment, status, position=None):
        """Met à jour le statut d'une assignation"""
        try:
            with transaction.atomic():
                old_status = assignment.status
                assignment.status = status
                
                if position:
                    assignment.last_location = {
                        'latitude': position.latitude,
                        'longitude': position.longitude,
                        'timestamp': position.timestamp.isoformat()
                    }
                
                assignment.save()

                # Logger le changement de statut
                if old_status != status:
                    self._log_status_change(assignment, old_status, status)

        except Exception as e:
            self.log_error(f"Error updating assignment status: {str(e)}", exc=e)

    def _handle_ending_assignment(self, assignment):
        """Gère une assignation qui se termine bientôt"""
        try:
            # 1. Vérifier si une extension est nécessaire
            if self._needs_extension(assignment):
                self._extend_assignment(assignment)
                return

            # 2. Vérifier si un remplacement est nécessaire
            if self._needs_replacement(assignment):
                self._prepare_replacement(assignment)

            # 3. Préparer la fin de l'assignation
            self._prepare_assignment_end(assignment)

        except Exception as e:
            self.log_error(f"Error handling ending assignment: {str(e)}", exc=e)

    def _needs_extension(self, assignment):
        """Vérifie si une assignation nécessite une extension"""
        # Vérifier les trips en cours ou prévus
        active_trips = Trip.objects.filter(
            vehicle=assignment.vehicle,
            status__in=['planned', 'in_progress'],
            planned_arrival__gt=assignment.assigned_until
        ).exists()

        return active_trips

    def _extend_assignment(self, assignment):
        """Prolonge une assignation"""
        try:
            with transaction.atomic():
                # Calculer la nouvelle durée
                latest_trip_end = Trip.objects.filter(
                    vehicle=assignment.vehicle,
                    status__in=['planned', 'in_progress']
                ).order_by('-planned_arrival').first()

                if latest_trip_end:
                    new_end = latest_trip_end.planned_arrival + timedelta(minutes=30)
                    assignment.assigned_until = new_end
                    assignment.save()

                    self.log_info(f"Extended assignment {assignment.id} until {new_end}")

        except Exception as e:
            self.log_error(f"Error extending assignment: {str(e)}", exc=e)

    def _needs_replacement(self, assignment):
        """Vérifie si un remplacement est nécessaire"""
        return Trip.objects.filter(
            vehicle=assignment.vehicle,
            status='planned',
            planned_departure__gt=assignment.assigned_until
        ).exists()

    def _prepare_replacement(self, assignment):
        """Prépare le remplacement d'une assignation"""
        try:
            # 1. Trouver les trips qui nécessitent un remplacement
            future_trips = Trip.objects.filter(
                vehicle=assignment.vehicle,
                status='planned',
                planned_departure__gt=assignment.assigned_until
            ).order_by('planned_departure')

            # 2. Chercher une nouvelle assignation disponible
            replacement = self._find_replacement_assignment(
                future_trips.first().planned_departure,
                future_trips.last().planned_arrival
            )

            # 3. Si trouvé, créer la nouvelle assignation
            if replacement:
                self._create_replacement_assignment(assignment, replacement, future_trips)

        except Exception as e:
            self.log_error(f"Error preparing replacement: {str(e)}", exc=e)

    def _get_upcoming_resource_needs(self):
        """Détermine les besoins en ressources à venir"""
        try:
            upcoming_trips = Trip.objects.filter(
                status='planned',
                planned_departure__gte=timezone.now(),
                planned_departure__lte=timezone.now() + timedelta(hours=24)
            ).order_by('planned_departure')

            needs = []
            for trip in upcoming_trips:
                needs.append({
                    'trip': trip,
                    'start_time': trip.planned_departure,
                    'end_time': trip.planned_arrival,
                    'route': trip.route,
                    'current_assignment': None
                })

            return needs

        except Exception as e:
            self.log_error(f"Error getting upcoming needs: {str(e)}", exc=e)
            return []

    def _get_available_assignments(self):
        """Récupère les assignations disponibles"""
        try:
            return DriverVehicleAssignment.objects.filter(
                status='active',
                assigned_until__gte=timezone.now()
            ).select_related('driver', 'vehicle')

        except Exception as e:
            self.log_error(f"Error getting available assignments: {str(e)}", exc=e)
            return []

    def _calculate_optimizations(self, needs, available):
        """Calcule les optimisations possibles"""
        optimizations = []
        
        for need in needs:
            best_assignment = self._find_best_assignment(need, available)
            if best_assignment:
                optimizations.append({
                    'need': need,
                    'current_assignment': need['current_assignment'],
                    'proposed_assignment': best_assignment,
                    'score': self._calculate_optimization_score(need, best_assignment)
                })

        return sorted(optimizations, key=lambda x: x['score'], reverse=True)

    def _find_best_assignment(self, need, available):
        """Trouve la meilleure assignation pour un besoin"""
        best_assignment = None
        best_score = -1

        for assignment in available:
            score = self._calculate_assignment_score(need, assignment)
            if score > best_score:
                best_score = score
                best_assignment = assignment

        return best_assignment

    def _calculate_assignment_score(self, need, assignment):
        """Calcule un score pour une assignation potentielle"""
        score = 0
        
        # Facteur 1: Expérience du chauffeur sur la route
        if need['route'] in assignment.driver.preferred_routes.all():
            score += 20

        # Facteur 2: Historique de performance
        score += min(assignment.driver.rating * 10, 50)

        # Facteur 3: Optimisation du temps
        if assignment.assigned_until <= need['start_time'] + timedelta(minutes=30):
            score += 15

        return score

    def _apply_assignment_changes(self, optimizations):
        """Applique les changements d'assignation optimisés"""
        try:
            with transaction.atomic():
                for opt in optimizations:
                    if opt['score'] > 50:  # Seuil minimal pour appliquer un changement
                        self._update_assignment(opt)

        except Exception as e:
            self.log_error(f"Error applying assignment changes: {str(e)}", exc=e)

    def _update_assignment(self, optimization):
        """Met à jour une assignation spécifique"""
        try:
            need = optimization['need']
            new_assignment = optimization['proposed_assignment']
            
            # Mettre à jour le trip
            trip = need['trip']
            trip.driver = new_assignment.driver
            trip.vehicle = new_assignment.vehicle
            trip.save()

            # Mettre à jour l'assignation
            if new_assignment.assigned_until < need['end_time']:
                new_assignment.assigned_until = need['end_time']
                new_assignment.save()

            self.log_info(f"Updated assignment for trip {trip.id}")

        except Exception as e:
            self.log_error(f"Error updating assignment: {str(e)}", exc=e)

    def get_fleet_status(self):
        """Retourne un résumé du statut de la flotte"""
        try:
            current_time = timezone.now()
            
            active_assignments = DriverVehicleAssignment.objects.filter(
                status='active',
                assigned_from__lte=current_time,
                assigned_until__gte=current_time
            ).count()

            total_trips = Trip.objects.filter(
                planned_departure__date=current_time.date()
            ).count()

            in_progress_trips = Trip.objects.filter(
                status='in_progress'
            ).count()

            return {
                'active_assignments': active_assignments,
                'total_trips_today': total_trips,
                'trips_in_progress': in_progress_trips,
                'timestamp': current_time.isoformat()
            }

        except Exception as e:
            self.log_error(f"Error getting fleet status: {str(e)}", exc=e)
            return {}