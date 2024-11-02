# membership_management/admin.py

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from .models import (
    CardAssignmentid,
    SubscriptionPlan,
    PassengerUser,
    CardInfo,
    Subscription,
    TransportCard,
    TemporaryVirtualCard,
    Payment,
    Balance,
    Transaction,
)
from django.utils.translation import gettext_lazy as _

# Custom filter for TransportCard validity
class IsValidFilter(SimpleListFilter):
    title = 'Validité de la Carte'
    parameter_name = 'is_valid'

    def lookups(self, request, model_admin):
        return (
            ('valid', 'Valide'),
            ('invalid', 'Invalide'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'valid':
            return queryset.filter(is_valid=True)
        if self.value() == 'invalid':
            return queryset.filter(is_valid=False)
        return queryset

# Admin for CardAssignmentid
@admin.register(CardAssignmentid)
class CardAssignmentidAdmin(admin.ModelAdmin):
    list_display = (
        'unique_code',
        'user_type',
        'status',
        'assigned_on',
    )
    search_fields = ('unique_code', 'user_type')
    list_filter = ('user_type', 'status', 'assigned_on')
    ordering = ('-assigned_on',)
    readonly_fields = ('assigned_on',)

    def save_model(self, request, obj, form, change):
        if not change and not obj.unique_code:
            obj.unique_code = self.generate_unique_code()
        super().save_model(request, obj, form, change)

    def generate_unique_code(self):
        import uuid
        return str(uuid.uuid4()).replace('-', '').upper()[:10]  # Example implementation

# Admin for SubscriptionPlan
@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        'user_type',
        'circuit',
        'locality',
        'duration',
        'price',
        'registration_fee',
    )
    search_fields = ('user_type', 'circuit', 'locality', 'duration')
    list_filter = ('user_type', 'circuit', 'locality', 'duration')
    ordering = ('user_type', 'circuit', 'locality', 'duration')

# Admin for PassengerUser
@admin.register(PassengerUser)
class PassengerUserAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'account_status',
        'emergency_contact',
        'created_at',
        'updated_at',
    )
    search_fields = ('user__username', 'account_status', 'emergency_contact')
    list_filter = ('account_status',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

# Admin for CardInfo
@admin.register(CardInfo)
class CardInfoAdmin(admin.ModelAdmin):
    list_display = (
        'card_assignment',
        'passenger',
        'card_type',
        'nfc_id',
        'issue_date',
        'expiry_date',
        'is_active',
        'created_at',
        'updated_at',
    )
    search_fields = (
        'card_assignment__unique_code',
        'passenger__user__username',
        'card_type',
        'nfc_id',
    )
    list_filter = ('card_type', 'is_active', 'issue_date', 'expiry_date')
    ordering = ('-issue_date',)
    readonly_fields = ('issue_date', 'created_at', 'updated_at')

# Admin for Subscription
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'passenger',
        'plan',
        'card',
        'start_date',
        'end_date',
        'status',
        'auto_renew',
        'created_at',
        'updated_at',
    )
    search_fields = (
        'passenger__user__username',
        'plan__user_type',
        'card__card_assignment__unique_code',
        'status',
    )
    list_filter = ('status', 'start_date', 'end_date', 'auto_renew')
    ordering = ('-start_date',)
    readonly_fields = ('created_at', 'updated_at')

# Admin for TransportCard
@admin.register(TransportCard)
class TransportCardAdmin(admin.ModelAdmin):
    list_display = (
        'card_info',
        'balance',
        'last_used',
        'created_at',
        'updated_at',
        'is_valid',
    )
    search_fields = (
        'card_info__card_assignment__unique_code',
        'card_info__passenger__user__username',
    )
    list_filter = ('last_used', IsValidFilter)
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'last_used')

    def is_valid(self, obj):
        return obj.is_valid()
    is_valid.boolean = True
    is_valid.short_description = 'Valide'

# Admin for TemporaryVirtualCard
@admin.register(TemporaryVirtualCard)
class TemporaryVirtualCardAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'passenger',
        'qr_code',
        'created_at',
        'expires_at',
        'is_used',
        'is_valid',
    )
    search_fields = (
        'passenger__user__username',
        'qr_code',
    )
    list_filter = ('is_used', 'expires_at')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'expires_at')

    def is_valid(self, obj):
        return obj.is_valid()
    is_valid.boolean = True
    is_valid.short_description = 'Valide'

# Admin for Payment
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'amount',
        'payment_type',
        'payment_date',
        'status',
        'subscription',
    )
    search_fields = (
        'user__username',
        'payment_type',
        'status',
        'subscription__id',
    )
    list_filter = ('payment_type', 'status', 'payment_date')
    ordering = ('-payment_date',)
    readonly_fields = ('payment_date',)

# Admin for Balance
@admin.register(Balance)
class BalanceAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'amount',
        'last_updated',
    )
    search_fields = ('user__username',)
    list_filter = ('last_updated',)
    ordering = ('-last_updated',)
    readonly_fields = ('last_updated',)

# Admin for Transaction
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'amount',
        'transaction_type',
        'description',
        'timestamp',
    )
    search_fields = (
        'user__username',
        'transaction_type',
        'description',
    )
    list_filter = ('transaction_type', 'timestamp')
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp',)
