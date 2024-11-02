# finance/admin.py

from django.contrib import admin
from .models import (
    Budget,
    Revenue,
    Expense,
    FinancialRecord,
    Invoice,
)
from django.utils.translation import gettext_lazy as _

# Administration pour Budget
@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'type',
        'start_date',
        'end_date',
        'total_amount',
        'remaining_amount',
        'created_by',
        'created_at',
        'updated_at',
    )
    search_fields = ('name', 'type', 'created_by__username')
    list_filter = ('type', 'start_date', 'end_date', 'created_by')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'remaining_amount')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.remaining_amount = obj.total_amount
        super().save_model(request, obj, form, change)

# Administration pour Revenue
@admin.register(Revenue)
class RevenueAdmin(admin.ModelAdmin):
    list_display = (
        'source',
        'amount',
        'date',
        'description',
        'recorded_by',
        'created_at',
    )
    search_fields = ('source', 'recorded_by__username', 'description')
    list_filter = ('source', 'date', 'recorded_by')
    ordering = ('-date',)
    readonly_fields = ('created_at',)

# Administration pour Expense
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'category',
        'amount',
        'date',
        'description',
        'approval_status',
        'approved_by',
        'recorded_by',
        'created_at',
        'updated_at',
    )
    search_fields = (
        'category',
        'approval_status',
        'approved_by__username',
        'recorded_by__username',
        'description',
    )
    list_filter = ('category', 'approval_status', 'date', 'approved_by', 'recorded_by')
    ordering = ('-date',)
    actions = ['approve_expenses', 'reject_expenses']

    def approve_expenses(self, request, queryset):
        updated = queryset.update(approval_status='approved', approved_by=request.user)
        self.message_user(request, f"{updated} dépense(s) approuvée(s).")
    approve_expenses.short_description = "Approuver les dépenses sélectionnées"

    def reject_expenses(self, request, queryset):
        updated = queryset.update(approval_status='rejected', approved_by=request.user)
        self.message_user(request, f"{updated} dépense(s) rejetée(s).")
    reject_expenses.short_description = "Rejeter les dépenses sélectionnées"

# Administration pour FinancialRecord
@admin.register(FinancialRecord)
class FinancialRecordAdmin(admin.ModelAdmin):
    list_display = (
        'record_type',
        'amount',
        'date',
        'description',
        'related_budget',
        'created_by',
        'created_at',
        'updated_at',
    )
    search_fields = (
        'record_type',
        'related_budget__name',
        'created_by__username',
        'description',
    )
    list_filter = ('record_type', 'date', 'related_budget', 'created_by')
    ordering = ('-date',)
    readonly_fields = ('created_at', 'updated_at')

# Administration pour Invoice
@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'client',
        'client_name',
        'issue_date',
        'due_date',
        'total_amount',
        'status',
        'created_by',
        'created_at',
        'updated_at',
    )
    search_fields = (
        'invoice_number',
        'client__username',
        'client_name_text',
        'status',
        'created_by__username',
    )
    list_filter = ('status', 'issue_date', 'due_date', 'created_by')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

    def client_name(self, obj):
        return obj.client_name
    client_name.short_description = 'Nom du Client'
