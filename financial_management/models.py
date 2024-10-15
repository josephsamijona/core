from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

class Budget(models.Model):
    BUDGET_TYPES = [
        ('annual', 'Annual'),
        ('quarterly', 'Quarterly'),
        ('monthly', 'Monthly'),
    ]

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=BUDGET_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    remaining_amount = models.DecimalField(max_digits=15, decimal_places=2)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.type} ({self.start_date} to {self.end_date})"

class Revenue(models.Model):
    REVENUE_SOURCES = [
        ('ticket_sales', 'Ticket Sales'),
        ('subscription', 'Subscription'),
        ('advertising', 'Advertising'),
        ('government_funding', 'Government Funding'),
        ('other', 'Other'),
    ]

    source = models.CharField(max_length=50, choices=REVENUE_SOURCES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()
    description = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source} - {self.amount} on {self.date}"

class Expense(models.Model):
    EXPENSE_CATEGORIES = [
        ('fuel', 'Fuel'),
        ('maintenance', 'Vehicle Maintenance'),
        ('salaries', 'Salaries'),
        ('insurance', 'Insurance'),
        ('utilities', 'Utilities'),
        ('other', 'Other'),
    ]

    APPROVAL_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    category = models.CharField(max_length=50, choices=EXPENSE_CATEGORIES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()
    description = models.TextField()
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS, default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_expenses')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_expenses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_category_display()} - {self.amount} on {self.date}"

class FinancialRecord(models.Model):
    RECORD_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('transfer', 'Transfer'),
        ('adjustment', 'Adjustment'),
    ]

    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()
    description = models.TextField()
    related_budget = models.ForeignKey(Budget, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.record_type} - {self.amount} on {self.date}"

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices',null=True)
    client_name_text = models.CharField(max_length=100, blank=True, null=True)  # Pour les cas où un nom textuel est nécessaire
    issue_date = models.DateField()
    due_date = models.DateField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_invoices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.client.username} ({self.status})"

    @property
    def client_name(self):
        return self.client.username if not self.client_name_text else self.client_name_text