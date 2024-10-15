from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from .models import Eleve, UserLog, Permission, User, Notification

class EleveInline(admin.TabularInline):
    model = Eleve
    extra = 1
    fk_name = 'parent'
    verbose_name = "Enfant"
    verbose_name_plural = "Enfants"

class UserAdmin(DefaultUserAdmin):
    list_display = ('username', 'email', 'user_type', 'is_active', 'last_login', 'date_joined')
    list_filter = ('user_type', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'telephone', 'address', 'date_of_birth', 'sex')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    inlines = [EleveInline]

    def save_model(self, request, obj, form, change):
        """Journaliser les modifications sensibles."""
        if change:  # Modification existante
            UserLog.objects.create(
                user=obj,
                action="Modification du profil par l'admin",
                ip_address=self.get_client_ip(request),
                details="L'utilisateur a été modifié depuis l'admin."
            )
        super().save_model(request, obj, form, change)

    @staticmethod
    def get_client_ip(request):
        """Récupère l'adresse IP du client."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

admin.site.register(User, UserAdmin)
admin.site.register(Permission)

class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'priority', 'created_at')
    list_filter = ('priority', 'notification_type')
    search_fields = ('message', 'user__username')

admin.site.register(Notification, NotificationAdmin)