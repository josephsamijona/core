# security/urls.py
from django.urls import path
from .views import ActiveSessionsView, TerminateSessionView, NotifyNewIPView, LoginAttemptView, CreateBackupView

urlpatterns = [
    path('sessions/', ActiveSessionsView.as_view(), name='active-sessions'),
    path('sessions/terminate/<str:session_key>/', TerminateSessionView.as_view(), name='terminate-session'),
    path('sessions/notify-new-ip/', NotifyNewIPView.as_view(), name='notify-new-ip'),
    path('login-attempt/', LoginAttemptView.as_view(), name='login-attempt'),
    path('backup/', CreateBackupView.as_view(), name='create-backup'),
]
