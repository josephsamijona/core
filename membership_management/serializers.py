# serializers.py
from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, PassengerUser, CardAssignmentid , CardInfo ,  TemporaryVirtualCard, Payment, Balance, Transaction

from financial_management.models import Revenue
from user_management.models import User
from django.utils import timezone
#from transport_management.models import PassengerTrip



class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'

class SubscriptionSerializer(serializers.ModelSerializer):
    plan_details = SubscriptionPlanSerializer(source='plan', read_only=True)
    passenger_name = serializers.CharField(source='passenger.user.get_full_name', read_only=True)

    class Meta:
        model = Subscription
        fields = ['id', 'passenger', 'plan', 'plan_details', 'passenger_name', 'card', 'start_date', 'end_date', 'status', 'auto_renew', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        subscription = Subscription.objects.create(**validated_data)
        self.generate_revenue(subscription)
        return subscription

    def generate_revenue(self, subscription):
        Revenue.objects.create(
            source='subscription',
            amount=subscription.plan.price,
            date=subscription.start_date,
            description=f"Subscription payment for {subscription.passenger.user.get_full_name()} - Plan: {subscription.plan}",
            recorded_by=self.context['request'].user
        )

class SubscriptionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['status', 'auto_renew']
        
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'user_type', 'sex', 'date_of_birth', 'telephone', 'address']
        read_only_fields = ['id', 'username', 'email', 'user_type']

class PassengerUserSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = PassengerUser
        fields = ['id', 'user', 'account_status', 'emergency_contact', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user_serializer = UserSerializer(instance.user, data=user_data, partial=True)
            if user_serializer.is_valid():
                user_serializer.save()
        return super(PassengerUserSerializer, self).update(instance, validated_data)
    
    
class CardAssignmentidSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardAssignmentid
        fields = ['id', 'user_type', 'unique_code', 'status', 'assigned_on']

class CardInfoSerializer(serializers.ModelSerializer):
    card_assignment = CardAssignmentidSerializer(read_only=True)
    passenger = PassengerUserSerializer(read_only=True)
    issue_date = serializers.DateField(default=timezone.now().date())

    class Meta:
        model = CardInfo
        fields = ['id', 'card_assignment', 'passenger', 'card_type', 'issue_date', 'expiry_date', 'is_active', 'nfc_id', 'is_mobile_nfc', 'mobile_device_id']

    def create(self, validated_data):
        # Assurez-vous que issue_date est une date, pas un datetime
        validated_data['issue_date'] = validated_data.get('issue_date', timezone.now().date())
        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['issue_date'] = instance.issue_date.isoformat()
        representation['expiry_date'] = instance.expiry_date.isoformat()
        return representation
        

class TemporaryVirtualCardSerializer(serializers.ModelSerializer):
    passenger = PassengerUserSerializer(read_only=True)

    class Meta:
        model = TemporaryVirtualCard
        fields = ['id', 'passenger', 'qr_code', 'created_at', 'expires_at', 'is_used']
        read_only_fields = ['id', 'created_at', 'expires_at', 'qr_code']
        
        
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'

class BalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Balance
        fields = '__all__'

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'
        
        
class CardValidationSerializer(serializers.Serializer):
    card_type = serializers.ChoiceField(choices=['physical', 'mobile_nfc', 'qr_code'])
    card_id = serializers.CharField()

class BoardingValidationSerializer(serializers.Serializer):
    card_data = CardValidationSerializer()
    trip_id = serializers.IntegerField()
    stop_id = serializers.IntegerField()

class AlightingValidationSerializer(serializers.Serializer):
    passenger_trip_id = serializers.IntegerField()
    stop_id = serializers.IntegerField()

class PassengerTripSerializer(serializers.ModelSerializer):
    class Meta:
        #model = PassengerTrip
        fields = ['id', 'passenger', 'trip', 'boarding_stop', 'alighting_stop', 'boarding_time', 'alighting_time', 'status', 'ocp']
