from django.apps import AppConfig


class TransportManagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport_management"
    
    def ready(self):
        import transport_management.signals
