# views.py
import qrcode
import io
import base64
from rest_framework.views import APIView
from decimal import Decimal
from django.core.files.base import ContentFile
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum
from django.db.models import Q
from django.db import transaction
from .models import SubscriptionPlan, Subscription, PassengerUser, CardAssignmentid , CardInfo ,  TemporaryVirtualCard, Payment, Balance, Transaction
from financial_management.models import Revenue
from .serializers import SubscriptionPlanSerializer, SubscriptionSerializer, SubscriptionUpdateSerializer, PassengerUserSerializer, CardAssignmentidSerializer, CardInfoSerializer, TemporaryVirtualCardSerializer, PaymentSerializer, BalanceSerializer, TransactionSerializer, BoardingValidationSerializer, AlightingValidationSerializer, PassengerTripSerializer

from user_management.models import User
from transport_management.models import Trip, Stop, PassengerTrip

class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]

class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return SubscriptionUpdateSerializer
        return SubscriptionSerializer

    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        subscription = self.get_object()
        if subscription.status != 'active':
            return Response({"error": "Only active subscriptions can be renewed."}, status=status.HTTP_400_BAD_REQUEST)
        
        subscription.end_date = subscription.end_date + timezone.timedelta(days=30)  # Assuming monthly renewal
        subscription.save()
        
        Revenue.objects.create(
            source='subscription',
            amount=subscription.plan.price,
            date=timezone.now().date(),
            description=f"Subscription renewal for {subscription.passenger.user.get_full_name()} - Plan: {subscription.plan}",
            recorded_by=request.user
        )
        
        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=False, methods=['get'])
    def active_subscriptions(self, request):
        active_subs = Subscription.objects.filter(
            status='active',
            end_date__gte=timezone.now().date()
        )
        serializer = self.get_serializer(active_subs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def subscription_revenue(self, request):
        revenue = Revenue.objects.filter(source='subscription').aggregate(total=Sum('amount'))
        return Response({"total_revenue": revenue['total'] or 0})
    
class PassengerUserViewSet(viewsets.ModelViewSet):
    queryset = PassengerUser.objects.all()
    serializer_class = PassengerUserSerializer

    @action(detail=False, methods=['get'])
    def by_user_type(self, request):
        user_type = request.query_params.get('type', None)
        if user_type is not None:
            passengers = PassengerUser.objects.filter(user__user_type=user_type)
            serializer = self.get_serializer(passengers, many=True)
            return Response(serializer.data)
        return Response({"error": "User type parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_account_status(self, request, pk=None):
        passenger = self.get_object()
        new_status = request.data.get('account_status', None)
        if new_status is not None and new_status in dict(PassengerUser.ACCOUNT_STATUS_CHOICES):
            passenger.account_status = new_status
            passenger.save()
            serializer = self.get_serializer(passenger)
            return Response(serializer.data)
        return Response({"error": "Invalid or missing account status"}, status=status.HTTP_400_BAD_REQUEST)
    
class CardAssignmentidViewSet(viewsets.ModelViewSet):
    queryset = CardAssignmentid.objects.all()
    serializer_class = CardAssignmentidSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        card_assignment = self.get_object()
        new_status = request.data.get('status')
        if new_status in dict(CardAssignmentid.STATUS_CHOICES).keys():
            card_assignment.status = new_status
            card_assignment.save()
            return Response({'status': 'Card assignment status updated'})
        return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

class CardInfoViewSet(viewsets.ModelViewSet):
    queryset = CardInfo.objects.all()
    serializer_class = CardInfoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        card_assignment_id = request.data.get('card_assignment')
        passenger_id = request.data.get('passenger')
        
        try:
            card_assignment = CardAssignmentid.objects.get(id=card_assignment_id)
            passenger = PassengerUser.objects.get(id=passenger_id)
        except (CardAssignmentid.DoesNotExist, PassengerUser.DoesNotExist):
            return Response({'error': 'Invalid card assignment or passenger'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(card_assignment=card_assignment, passenger=passenger)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        card = self.get_object()
        card.is_active = not card.is_active
        card.save()
        return Response({'status': 'Card active status toggled', 'is_active': card.is_active})

    @action(detail=True, methods=['post'])
    def enable_mobile_nfc(self, request, pk=None):
        card = self.get_object()
        device_id = request.data.get('device_id')
        if device_id:
            card.is_mobile_nfc = True
            card.mobile_device_id = device_id
            card.save()
            return Response({'status': 'Mobile NFC enabled', 'device_id': card.mobile_device_id})
        return Response({'error': 'Device ID is required'}, status=status.HTTP_400_BAD_REQUEST)

class TemporaryVirtualCardViewSet(viewsets.ModelViewSet):
    queryset = TemporaryVirtualCard.objects.all()
    serializer_class = TemporaryVirtualCardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def generate_qr_code(self, data):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()

    @action(detail=False, methods=['post'])
    def generate(self, request):
        passenger_id = request.data.get('passenger_id')
        if passenger_id:
            try:
                passenger = PassengerUser.objects.get(id=passenger_id)
            except PassengerUser.DoesNotExist:
                return Response({'error': 'Passenger not found'}, status=status.HTTP_404_NOT_FOUND)
            
            unique_code = f"TEMP-{timezone.now().timestamp()}"
            qr_code_data = self.generate_qr_code(unique_code)
            virtual_card = TemporaryVirtualCard.objects.create(
                passenger=passenger,
                qr_code=unique_code,
                expires_at=timezone.now() + timezone.timedelta(hours=24)
            )
            return Response({
                'virtual_card': TemporaryVirtualCardSerializer(virtual_card).data,
                'qr_code': qr_code_data
            })
        return Response({'error': 'Passenger ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def use_card(self, request, pk=None):
        card = self.get_object()
        if card.is_valid():
            card.is_used = True
            card.save()
            return Response({'status': 'Virtual card used successfully'})
        return Response({'error': 'Card is invalid or expired'}, status=status.HTTP_400_BAD_REQUEST)
    
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    @action(detail=False, methods=['post'])
    def process_payment(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            payment = serializer.save()
            user = payment.user
            
            if payment.payment_type in ['subscription', 'registration']:
                # Traitement pour abonnement ou frais d'inscription
                payment.status = 'completed'
                payment.save()
                
                if payment.payment_type == 'subscription':
                    # Mise à jour de l'abonnement
                    subscription = payment.subscription
                    subscription.is_active = True
                    subscription.save()
            
            elif payment.payment_type == 'top_up':
                # Rechargement du solde
                balance, created = Balance.objects.get_or_create(user=user)
                balance.amount += payment.amount
                balance.save()
                
                Transaction.objects.create(
                    user=user,
                    amount=payment.amount,
                    transaction_type='credit',
                    description='Rechargement du solde'
                )
                
                payment.status = 'completed'
                payment.save()
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class BalanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Balance.objects.all()
    serializer_class = BalanceSerializer

    @action(detail=True, methods=['post'])
    def update_balance(self, request, pk=None):
        balance = self.get_object()
        amount = Decimal(request.data.get('amount', '0'))
        description = request.data.get('description', '')

        with transaction.atomic():
            if balance.amount >= amount:
                balance.amount -= amount
                balance.save()

                Transaction.objects.create(
                    user=balance.user,
                    amount=amount,
                    transaction_type='debit',
                    description=description
                )

                return Response({'message': 'Balance updated successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Insufficient balance'}, status=status.HTTP_400_BAD_REQUEST)

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    
class BoardingValidationView(APIView):
    def post(self, request):
        serializer = BoardingValidationSerializer(data=request.data)
        if serializer.is_valid():
            card_data = serializer.validated_data['card_data']
            trip_id = serializer.validated_data['trip_id']
            stop_id = serializer.validated_data['stop_id']

            passenger = self.validate_card(card_data)
            if not passenger:
                return Response({"error": "Carte invalide"}, status=status.HTTP_400_BAD_REQUEST)

            if not self.has_valid_subscription(passenger, stop_id):
                return Response({"error": "Pas d'abonnement valide pour cette localité"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                trip = Trip.objects.get(id=trip_id)
                boarding_stop = Stop.objects.get(id=stop_id)
                passenger_trip = PassengerTrip.objects.create(
                    passenger=passenger.user,
                    trip=trip,
                    boarding_stop=boarding_stop,
                    ocp=trip.ocp,  # Assurez-vous que le Trip a bien un champ ocp
                    status='boarded'
                )

                serializer = PassengerTripSerializer(passenger_trip)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except (Trip.DoesNotExist, Stop.DoesNotExist):
                return Response({"error": "Trajet ou arrêt invalide"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def validate_card(self, card_data):
        try:
            card_info = CardInfo.objects.get(id=card_data['card_id'], is_active=True)
            return card_info.passenger
        except CardInfo.DoesNotExist:
            return None

    def has_valid_subscription(self, passenger, stop_id):
        stop = Stop.objects.get(id=stop_id)
        active_subscriptions = Subscription.objects.filter(
            passenger=passenger,
            status='active',
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        )
        for subscription in active_subscriptions:
            if subscription.plan.locality == stop.service_zone and subscription.plan.circuit == stop.circuit:
                return True
        return False

class AlightingValidationView(APIView):
    def post(self, request):
        serializer = AlightingValidationSerializer(data=request.data)
        if serializer.is_valid():
            passenger_trip_id = serializer.validated_data['passenger_trip_id']
            stop_id = serializer.validated_data['stop_id']

            try:
                passenger_trip = PassengerTrip.objects.get(id=passenger_trip_id, status='boarded')
                alighting_stop = Stop.objects.get(id=stop_id)

                passenger_trip.alighting_stop = alighting_stop
                passenger_trip.alighting_time = timezone.now()
                passenger_trip.status = 'completed'
                passenger_trip.save()

                serializer = PassengerTripSerializer(passenger_trip)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except PassengerTrip.DoesNotExist:
                return Response({"error": "Trajet passager invalide ou déjà terminé"}, status=status.HTTP_400_BAD_REQUEST)
            except Stop.DoesNotExist:
                return Response({"error": "Arrêt invalide"}, status=status.HTTP_400_BAD_REQUEST)