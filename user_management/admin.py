# admin.py

from django.contrib import admin
from .models import (
    User,
    Eleve,
    Permission,
    DeviceInfo,
    Notification,
    Feedback,
    UserLog,
)
from django.contrib.auth import get_user_model

User = get_user_model()

admin.site.unregister(User)
# Configuration de l'admin pour User
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'user_type', 'email', 'first_name', 'last_name', 'sex', 'date_of_birth')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('user_type', 'sex', 'date_of_birth')
    ordering = ('username',)

# Configuration de l'admin pour Eleve
@admin.register(Eleve)
class EleveAdmin(admin.ModelAdmin):
    list_display = ('user', 'classe', 'numero_etudiant', 'parent')
    search_fields = ('user__username', 'classe', 'numero_etudiant')
    list_filter = ('classe',)

# Configuration de l'admin pour Permission
@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

# Configuration de l'admin pour DeviceInfo
@admin.register(DeviceInfo)
class DeviceInfoAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_name', 'device_type', 'last_login')
    search_fields = ('user__username', 'device_name', 'device_type')
    list_filter = ('device_type',)

# Configuration de l'admin pour Notification
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'priority', 'created_at', 'read')
    search_fields = ('user__username', 'message')
    list_filter = ('notification_type', 'priority', 'read')
    ordering = ('-created_at',)
    actions = ['mark_notifications_as_read']

    def mark_notifications_as_read(self, request, queryset):
        queryset.update(read=True)
    mark_notifications_as_read.short_description = "Marquer les notifications sélectionnées comme lues"

# Configuration de l'admin pour Feedback
@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'rating', 'created_at')
    search_fields = ('user__username', 'content')
    list_filter = ('rating', 'created_at')

# Configuration de l'admin pour UserLog
@admin.register(UserLog)
class UserLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp', 'ip_address')
    search_fields = ('user__username', 'action', 'ip_address')
    list_filter = ('timestamp',)

