# security/serializers.py
from rest_framework import serializers
from .models import SessionManagement, LoginAttempt

class SessionManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionManagement
        fields = ['id', 'user', 'session_key', 'ip_address', 'user_agent', 
                  'login_time', 'last_activity', 'is_active']

class LoginAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginAttempt
        fields = ['user', 'ip_address', 'timestamp', 'success', 'user_agent']