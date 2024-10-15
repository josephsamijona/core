from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BudgetViewSet, RevenueViewSet, ExpenseViewSet, FinancialRecordViewSet, InvoiceViewSet , FinancialReportView

router = DefaultRouter()
router.register(r'budgets', BudgetViewSet)
router.register(r'revenues', RevenueViewSet)
router.register(r'expenses', ExpenseViewSet)
router.register(r'financial-records', FinancialRecordViewSet)
router.register(r'invoices', InvoiceViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('financial-reports/', FinancialReportView.as_view(), name='financial-reports'),
]