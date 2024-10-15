# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubscriptionPlanViewSet, SubscriptionViewSet , PassengerUserViewSet, CardAssignmentidViewSet, CardInfoViewSet, AlightingValidationView,TemporaryVirtualCardViewSet,BoardingValidationView, PaymentViewSet, BalanceViewSet, TransactionViewSet

router = DefaultRouter()
router.register(r'subscription-plans', SubscriptionPlanViewSet)
router.register(r'subscriptions', SubscriptionViewSet)
router.register(r'passengers', PassengerUserViewSet)
router.register(r'card-assignments', CardAssignmentidViewSet)
router.register(r'cards', CardInfoViewSet)
router.register(r'virtual-cards', TemporaryVirtualCardViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'balances', BalanceViewSet)
router.register(r'transactions', TransactionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('api/validate-boarding/', BoardingValidationView.as_view(), name='validate_boarding'),
    path('api/validate-alighting/', AlightingValidationView.as_view(), name='validate_alighting'),
]