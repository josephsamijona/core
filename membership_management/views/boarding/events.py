
from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from datetime import datetime
from django.utils import timezone
from enum import Enum

class BoardingEventType(Enum):
    # Événements de Session
    SESSION_INITIALIZED = "boarding.session.initialized"
    SESSION_STARTED = "boarding.session.started"
    SESSION_PAUSED = "boarding.session.paused"
    SESSION_RESUMED = "boarding.session.resumed"
    SESSION_ENDED = "boarding.session.ended"
    
    # Événements de Trip
    TRIP_STARTED = "boarding.trip.started"
    TRIP_UPDATED = "boarding.trip.updated"
    TRIP_ENDED = "boarding.trip.ended"
    TRIP_DELAYED = "boarding.trip.delayed"
    
    # Événements de Validation
    CARD_SCANNED = "boarding.validation.card_scanned"
    QR_SCANNED = "boarding.validation.qr_scanned"
    VALIDATION_SUCCEEDED = "boarding.validation.succeeded"
    VALIDATION_FAILED = "boarding.validation.failed"
    VALIDATION_RETRY = "boarding.validation.retry"
    
    # Événements Passager
    PASSENGER_BOARDING = "boarding.passenger.boarding"
    PASSENGER_BOARDED = "boarding.passenger.boarded"
    PASSENGER_DENIED = "boarding.passenger.denied"
    PASSENGER_ALIGHTING = "boarding.passenger.alighting"
    PASSENGER_ALIGHTED = "boarding.passenger.alighted"
    
    # Événements Stop/Station
    STOP_REACHED = "boarding.stop.reached"
    STOP_DEPARTED = "boarding.stop.departed"
    STOP_SKIPPED = "boarding.stop.skipped"
    
    # Événements Device
    DEVICE_CONNECTED = "boarding.device.connected"
    DEVICE_DISCONNECTED = "boarding.device.disconnected"
    DEVICE_ERROR = "boarding.device.error"
    
    # Événements Sync
    SYNC_STARTED = "boarding.sync.started"
    SYNC_COMPLETED = "boarding.sync.completed"
    SYNC_FAILED = "boarding.sync.failed"
    
    # Événements Erreur/Monitoring
    ERROR_OCCURRED = "boarding.error.occurred"
    CAPACITY_WARNING = "boarding.capacity.warning"
    CAPACITY_EXCEEDED = "boarding.capacity.exceeded"
    INCIDENT_REPORTED = "boarding.incident.reported"

@dataclass
class BoardingEvent:
    """Représentation d'un événement de boarding"""
    type: BoardingEventType
    data: dict
    timestamp: datetime = None
    source: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()

class BoardingEventDispatcher:
    """Gestionnaire central des événements de boarding"""
    
    def __init__(self):
        self._handlers: Dict[BoardingEventType, List[Callable]] = {}
        self._event_history: List[BoardingEvent] = []
        self.max_history_size = 1000
    
    def subscribe(self, event_type: BoardingEventType, handler: Callable[[BoardingEvent], None]) -> None:
        """Souscrit un handler à un type d'événement"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: BoardingEventType, handler: Callable[[BoardingEvent], None]) -> None:
        """Désinscrit un handler d'un type d'événement"""
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
    
    def dispatch(self, event: BoardingEvent) -> None:
        """Dispatch un événement à tous les handlers enregistrés"""
        # Ajouter à l'historique
        self._add_to_history(event)
        
        # Notifier les handlers
        if event.type in self._handlers:
            for handler in self._handlers[event.type]:
                try:
                    handler(event)
                except Exception as e:
                    self._handle_error(e, event)
    
    def dispatch_multiple(self, events: List[BoardingEvent]) -> None:
        """Dispatch plusieurs événements dans l'ordre"""
        for event in events:
            self.dispatch(event)
    
    def _add_to_history(self, event: BoardingEvent) -> None:
        """Ajoute un événement à l'historique avec gestion de la taille"""
        self._event_history.append(event)
        if len(self._event_history) > self.max_history_size:
            self._event_history = self._event_history[-self.max_history_size:]
    
    def _handle_error(self, error: Exception, event: BoardingEvent) -> None:
        """Gère les erreurs de dispatch"""
        error_event = BoardingEvent(
            type=BoardingEventType.ERROR_OCCURRED,
            data={
                'error_type': type(error).__name__,
                'error_message': str(error),
                'original_event': {
                    'type': event.type.value,
                    'data': event.data,
                    'timestamp': event.timestamp,
                    'source': event.source
                }
            }
        )
        self.dispatch(error_event)
    
    def get_recent_events(self, event_type: BoardingEventType = None, limit: int = 10) -> List[BoardingEvent]:
        """Récupère les événements récents avec filtrage optionnel"""
        if event_type:
            filtered_events = [e for e in self._event_history if e.type == event_type]
            return filtered_events[-limit:]
        return self._event_history[-limit:]

class BoardingEventHandler:
    """Classe de base pour les handlers d'événements"""
    
    def __init__(self, dispatcher: BoardingEventDispatcher):
        self.dispatcher = dispatcher
        self.register_handlers()
    
    def register_handlers(self):
        """À surcharger pour enregistrer les handlers"""
        pass
    
    def handle_event(self, event: BoardingEvent):
        """À surcharger pour le traitement des événements"""
        pass

# Instance globale du dispatcher
event_dispatcher = BoardingEventDispatcher()

def get_event_dispatcher() -> BoardingEventDispatcher:
    """Récupère l'instance globale du dispatcher"""
    return event_dispatcher

# Exemple d'utilisation d'un handler spécifique
class BoardingSessionHandler(BoardingEventHandler):
    def register_handlers(self):
        self.dispatcher.subscribe(BoardingEventType.SESSION_INITIALIZED, self.handle_session_init)
        self.dispatcher.subscribe(BoardingEventType.SESSION_ENDED, self.handle_session_end)
    
    def handle_session_init(self, event: BoardingEvent):
        """Gère l'initialisation d'une session"""
        session_data = event.data
        # Logique de gestion de l'initialisation
    
    def handle_session_end(self, event: BoardingEvent):
        """Gère la fin d'une session"""
        session_data = event.data
        # Logique de gestion de la fin de session
