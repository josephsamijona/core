# admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    BlockedIP,
    LoginAttempt,
    UserActivityLog,
    AuditLog,
    LoginHistory,
    AccessControlList,
    SecurityIncident,
    DataRetentionPolicy,
    EncryptionKey,
    SystemHealthCheck,
    AccessLog,
    SessionManagement,
    TokenBlacklist,
    PasswordChangeHistory,
    ConfigurationChangeLog,
    IPWhitelist,
    UserConsent,
    AnomalyDetection,
    BackupLog
)

# Exemple d'administration personnalisée pour BlockedIP
@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'reason', 'blocked_at', 'unblock_at', 'attempt_count', 'is_blocked')
    search_fields = ('ip_address', 'reason')
    list_filter = ('blocked_at', 'unblock_at')
    readonly_fields = ('blocked_at',)

    def is_blocked(self, obj):
        return obj.is_blocked()
    is_blocked.boolean = True
    is_blocked.short_description = 'Bloqué'

# Administration pour LoginAttempt
@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'timestamp', 'success', 'country')
    search_fields = ('user__username', 'ip_address', 'country')
    list_filter = ('success', 'timestamp', 'country')

# Administration pour UserActivityLog
@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'timestamp', 'ip_address')
    search_fields = ('user__username', 'activity_type', 'description')
    list_filter = ('activity_type', 'timestamp')

# Administration pour AuditLog
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'object_id', 'timestamp')
    search_fields = ('user__username', 'action', 'model_name')
    list_filter = ('action', 'model_name', 'timestamp')

# Administration pour LoginHistory
@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_time', 'logout_time', 'ip_address', 'session_duration')
    search_fields = ('user__username', 'ip_address')
    list_filter = ('login_time', 'logout_time')

# Administration pour AccessControlList
@admin.register(AccessControlList)
class AccessControlListAdmin(admin.ModelAdmin):
    list_display = ('user', 'resource', 'permission', 'expires_at')
    search_fields = ('user__username', 'resource', 'permission')
    list_filter = ('permission', 'expires_at')

# Administration pour SecurityIncident
@admin.register(SecurityIncident)
class SecurityIncidentAdmin(admin.ModelAdmin):
    list_display = ('title', 'severity', 'reported_by', 'status', 'reported_at', 'resolved_at')
    search_fields = ('title', 'description', 'reported_by__username')
    list_filter = ('severity', 'status', 'reported_at')

# Administration pour DataRetentionPolicy
@admin.register(DataRetentionPolicy)
class DataRetentionPolicyAdmin(admin.ModelAdmin):
    list_display = ('data_type', 'retention_period', 'last_updated')
    search_fields = ('data_type',)
    list_filter = ('retention_period', 'last_updated')

# Administration pour EncryptionKey
@admin.register(EncryptionKey)
class EncryptionKeyAdmin(admin.ModelAdmin):
    list_display = ('key_identifier', 'key_type', 'created_at', 'expires_at', 'is_active', 'is_compromised')
    search_fields = ('key_identifier', 'key_type')
    list_filter = ('key_type', 'is_active', 'is_compromised')

# Administration pour SystemHealthCheck
@admin.register(SystemHealthCheck)
class SystemHealthCheckAdmin(admin.ModelAdmin):
    list_display = ('check_type', 'status', 'checked_at')
    search_fields = ('check_type', 'details')
    list_filter = ('status', 'check_type', 'checked_at')

# Administration pour AccessLog
@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'resource', 'action', 'timestamp', 'ip_address', 'success')
    search_fields = ('user__username', 'resource', 'action', 'ip_address')
    list_filter = ('action', 'success', 'timestamp')

# Administration pour SessionManagement
@admin.register(SessionManagement)
class SessionManagementAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_key', 'ip_address', 'login_time', 'last_activity', 'is_active')
    search_fields = ('user__username', 'session_key', 'ip_address')
    list_filter = ('is_active', 'login_time', 'last_activity')

# Administration pour TokenBlacklist
@admin.register(TokenBlacklist)
class TokenBlacklistAdmin(admin.ModelAdmin):
    list_display = ('token_preview', 'reason', 'revoked_at', 'expires_at')
    search_fields = ('token', 'reason')
    list_filter = ('revoked_at', 'expires_at')

    def token_preview(self, obj):
        return format_html(f"{obj.token[:20]}...")

    token_preview.short_description = 'Token'

# Administration pour PasswordChangeHistory
@admin.register(PasswordChangeHistory)
class PasswordChangeHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'changed_at')
    search_fields = ('user__username',)
    list_filter = ('changed_at',)

# Administration pour ConfigurationChangeLog
@admin.register(ConfigurationChangeLog)
class ConfigurationChangeLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'parameter', 'changed_at')
    search_fields = ('user__username', 'parameter')
    list_filter = ('parameter', 'changed_at')

# Administration pour IPWhitelist
@admin.register(IPWhitelist)
class IPWhitelistAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'description', 'added_at', 'expires_at')
    search_fields = ('ip_address', 'description')
    list_filter = ('added_at', 'expires_at')

# Administration pour UserConsent
@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = ('user', 'consent_type', 'given_at', 'ip_address')
    search_fields = ('user__username', 'consent_type')
    list_filter = ('consent_type', 'given_at')

# Administration pour AnomalyDetection
@admin.register(AnomalyDetection)
class AnomalyDetectionAdmin(admin.ModelAdmin):
    list_display = ('user', 'anomaly_type', 'detected_at', 'resolved')
    search_fields = ('user__username', 'anomaly_type', 'description')
    list_filter = ('anomaly_type', 'resolved', 'detected_at')

# Administration pour BackupLog
@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    list_display = ('backup_type', 'status', 'started_at', 'completed_at')
    search_fields = ('backup_type', 'status')
    list_filter = ('backup_type', 'status', 'started_at', 'completed_at')

# Optionnel : Personnaliser l'affichage de l'utilisateur
from django.contrib.auth import get_user_model
User = get_user_model()

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_active', 'date_joined')

