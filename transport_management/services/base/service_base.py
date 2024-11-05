# transport_management/services/base/service_base.py

from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ServiceBase:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def log_info(self, message):
        self.logger.info(message)

    def log_error(self, message, exc=None):
        self.logger.error(message, exc_info=exc)

    def log_warning(self, message):
        self.logger.warning(message)