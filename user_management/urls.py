from django.urls import path
from .views import UserRegistrationView
from .views import LoginView, LogoutView, ChildAccessView
from .views import PasswordResetView, PasswordResetConfirmView, ProfileUpdateView, SuspendUserView,DeviceListView, LogoutDeviceView, SendNotificationView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,  # Connexion avec JWT
    TokenRefreshView,  # Rafraîchir le token
)

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('child-access/', ChildAccessView.as_view(), name='child-access'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('password-reset/', PasswordResetView.as_view(), name='password_reset'),
    path('password-reset-confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('profile/update/', ProfileUpdateView.as_view(), name='profile_update'),
    path('user/suspend/<int:pk>/', SuspendUserView.as_view(), name='user-suspend'),
    path('devices/', DeviceListView.as_view(), name='device-list'),
    path('devices/logout/', LogoutDeviceView.as_view(), name='device-logout'),
    path('notifications/send/', SendNotificationView.as_view(), name='send-notification'),
]

