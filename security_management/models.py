from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

### MODELS ORIGINAUX

class BlockedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    reason = models.TextField()
    blocked_at = models.DateTimeField(auto_now_add=True)
    unblock_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)

    def is_blocked(self):
        """Vérifie si l'IP est encore bloquée."""
        return self.unblock_at is None or timezone.now() < self.unblock_at

    def __str__(self):
        return f"Blocked IP: {self.ip_address} - Blocked until {self.unblock_at}"


class LoginAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField()
    user_agent = models.TextField()
    country = models.CharField(max_length=100, blank=True, null=True)  # Enrichir avec GeoIP

    def __str__(self):
        return f"Login attempt by {self.user or 'Unknown'} from {self.ip_address}"


class UserActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=100)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()

    def __str__(self):
        return f"{self.user}'s activity: {self.activity_type}"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    object_id = models.PositiveIntegerField()
    changes = models.JSONField()
    session_id = models.CharField(max_length=100, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Audit: {self.user} - {self.action} on {self.model_name}"


class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    login_time = models.DateTimeField()
    logout_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    session_id = models.CharField(max_length=100)
    session_duration = models.DurationField(blank=True, null=True)  # Calculer la durée de session

    def __str__(self):
        return f"{self.user}'s login at {self.login_time}"


class AccessControlList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    resource = models.CharField(max_length=100)
    permission = models.CharField(max_length=20)  # e.g., "read", "write", "delete"
    expires_at = models.DateTimeField(null=True, blank=True)  # Permissions temporaires

    class Meta:
        unique_together = ('user', 'resource', 'permission')

    def __str__(self):
        return f"{self.user} - {self.permission} on {self.resource}"


class SecurityIncident(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.CharField(
        max_length=15,
        choices=[('open', 'Open'), ('in-progress', 'In Progress'), ('resolved', 'Resolved')],
        default='open'
    )
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.title} - {self.severity}"


class DataRetentionPolicy(models.Model):
    data_type = models.CharField(max_length=100, unique=True)
    retention_period = models.PositiveIntegerField(help_text="Retention period in days")
    description = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.data_type} - {self.retention_period} days"


class EncryptionKey(models.Model):
    key_identifier = models.CharField(max_length=100, unique=True)
    key_type = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_compromised = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.key_identifier} - {self.key_type}"


class SystemHealthCheck(models.Model):
    STATUS_CHOICES = [
        ('normal', 'Normal'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    check_type = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    details = models.TextField()
    check_url = models.URLField(blank=True, null=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.check_type} - {self.status}"


class AccessLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    resource = models.CharField(max_length=200)
    action = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    success = models.BooleanField()
    user_agent = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user} accessed {self.resource} - {self.action}"


### NOUVEAUX MODELS

class SessionManagement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=100, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    login_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Session for {self.user} from {self.ip_address}"

    def end_session(self):
        self.is_active = False
        self.save()


class TokenBlacklist(models.Model):
    token = models.CharField(max_length=200, unique=True)
    reason = models.CharField(max_length=200)
    revoked_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Revoked token: {self.token[:20]}..."


class PasswordChangeHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    changed_at = models.DateTimeField(auto_now_add=True)
    previous_password_hash = models.CharField(max_length=256)

    def __str__(self):
        return f"{self.user}'s password changed at {self.changed_at}"


class ConfigurationChangeLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    parameter = models.CharField(max_length=100)
    old_value = models.TextField()
    new_value = models.TextField()
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Configuration change by {self.user} on {self.parameter}"


class IPWhitelist(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    description = models.CharField(max_length=200, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Whitelisted IP: {self.ip_address}"


class UserConsent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    consent_type = models.CharField(max_length=100)
    given_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()

    def __str__(self):
        return f"Consent for {self.consent_type} by {self.user}"


class AnomalyDetection(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    anomaly_type = models.CharField(max_length=100)
    description = models.TextField()
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Anomaly detected: {self.anomaly_type} for {self.user}"


class BackupLog(models.Model):
    backup_type = models.CharField(max_length=100)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=[('success', 'Success'), ('failed', 'Failed')])

    def __str__(self):
        return f"Backup {self.backup_type} - {self.status}"
