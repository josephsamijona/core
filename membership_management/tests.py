# tests.py
from django.test import TestCase
from django.urls import reverse
from user_management.models import User
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
import uuid
from django.test import TransactionTestCase
from transport_management.models import Trip, Stop, PassengerTrip, Route, OperationalControlPlan, RouteStop, Driver
from .models import SubscriptionPlan, Subscription, PassengerUser, CardAssignmentid, CardInfo, TemporaryVirtualCard, Payment, Balance, Transaction, UserType, Status
from financial_management.models import Revenue
from django.utils import timezone
from inventory_management.models import Vehicle
 

class SubscriptionAPITestCase(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass',
            email='test@example.com',
            user_type='etudiant',
            sex='M',
            date_of_birth='2000-01-01',
            telephone='1234567890',
            address='Test Address'
        )
        self.passenger = PassengerUser.objects.get(user=self.user)  # Le PassengerUser est créé automatiquement
        self.client.force_authenticate(user=self.user)
        
        self.plan = SubscriptionPlan.objects.create(
            user_type='student',
            circuit='A',
            locality='TestCity',
            duration='monthly',
            price=100.00
        )
        
    def test_create_subscription(self):
        data = {
            'passenger': self.passenger.id,
            'plan': self.plan.id,
            'start_date': '2023-01-01',
            'end_date': '2023-02-01',
        }
        response = self.client.post('/api/membership/subscriptions/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Subscription.objects.count(), 1)

    def test_renew_subscription(self):
        subscription = Subscription.objects.create(
            passenger=self.passenger,
            plan=self.plan,
            start_date='2023-01-01',
            end_date='2023-02-01',
            status='active'
        )
        response = self.client.post(f'/api/membership/subscriptions/{subscription.id}/renew/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Revenue.objects.count(), 1)

    def test_get_active_subscriptions(self):
        today = timezone.now().date()
        subscription = Subscription.objects.create(
            passenger=self.passenger,
            plan=self.plan,
            start_date=today,
            end_date=today + timezone.timedelta(days=30),
            status='active'
        )
        
        # Vérifiez que l'abonnement a bien été créé
        self.assertTrue(Subscription.objects.filter(id=subscription.id).exists())
        
        response = self.client.get('/api/membership/subscriptions/active_subscriptions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Imprimez les données de réponse pour le débogage
        print("Response data:", response.data)
        
        self.assertEqual(len(response.data), 1)

    def test_get_subscription_revenue(self):
        subscription = Subscription.objects.create(
            passenger=self.passenger,
            plan=self.plan,
            start_date='2023-01-01',
            end_date='2023-02-01',
            status='active'
        )
        
        # Créer manuellement une entrée de revenu pour ce test
        Revenue.objects.create(
            source='subscription',
            amount=self.plan.price,
            date=subscription.start_date,
            description=f"Subscription payment for {subscription.passenger.user.get_full_name()} - Plan: {subscription.plan}",
            recorded_by=self.user
        )
        
        response = self.client.get('/api/membership/subscriptions/subscription_revenue/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_revenue'], 100.00)
        
class PassengerUserAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass',
            email='test@example.com',
            user_type='etudiant',
            sex='M',
            date_of_birth='2000-01-01',
            telephone='1234567890',
            address='Test Address'
        )
        self.client.force_authenticate(user=self.user)

    def test_passenger_user_auto_creation(self):
        self.assertTrue(PassengerUser.objects.filter(user=self.user).exists())
        passenger = PassengerUser.objects.get(user=self.user)
        self.assertEqual(passenger.account_status, 'active')

    def test_update_passenger_user(self):
        passenger = PassengerUser.objects.get(user=self.user)
        data = {
            "user": {
                "first_name": "Updated",
                "last_name": "Name"
            },
            "emergency_contact": "New Emergency Contact"
        }
        response = self.client.patch(f'/api/membership/passengers/{passenger.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        passenger.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(passenger.emergency_contact, "New Emergency Contact")

    def test_get_passengers_by_user_type(self):
        response = self.client.get('/api/membership/passengers/by_user_type/?type=etudiant')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_update_account_status(self):
        passenger = PassengerUser.objects.get(user=self.user)
        data = {"account_status": "inactive"}
        response = self.client.patch(f'/api/membership/passengers/{passenger.id}/update_account_status/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        passenger.refresh_from_db()
        self.assertEqual(passenger.account_status, 'inactive')
        


class CardManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username=f'testuser_{timezone.now().timestamp()}',
            password='testpass',
            email=f'testuser_{timezone.now().timestamp()}@example.com',
            user_type='S'  # Use 'S' for Student, 'P' for Parent, 'E' for Employee
        )
        self.client.force_authenticate(user=self.user)
        self.passenger = PassengerUser.objects.create(user=self.user, account_status='active')

    def create_card_assignment(self):
        return CardAssignmentid.objects.create(
            user_type='S',  # Use 'S' for Student, 'P' for Parent, 'E' for Employee
            unique_code=f'TEST{timezone.now().timestamp()}',
            status='available'
        )

    def test_create_card_info(self):
        card_assignment = self.create_card_assignment()
        url = reverse('cardinfo-list')
        data = {
            'card_assignment': card_assignment.id,
            'passenger': self.passenger.id,
            'card_type': 'rfid',
            'expiry_date': '2025-01-01',
            'issue_date': timezone.now().date().isoformat()  # Ajoutez cette ligne
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CardInfo.objects.count(), 1)

    def test_toggle_card_active_status(self):
        card_assignment = self.create_card_assignment()
        card_info = CardInfo.objects.create(
            card_assignment=card_assignment,
            passenger=self.passenger,
            card_type='rfid',
            expiry_date='2025-01-01',
            is_active=True
        )
        url = reverse('cardinfo-toggle-active', kwargs={'pk': card_info.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        card_info.refresh_from_db()
        self.assertFalse(card_info.is_active)

    def test_enable_mobile_nfc(self):
        card_assignment = self.create_card_assignment()
        card_info = CardInfo.objects.create(
            card_assignment=card_assignment,
            passenger=self.passenger,
            card_type='nfc',
            expiry_date='2025-01-01'
        )
        url = reverse('cardinfo-enable-mobile-nfc', kwargs={'pk': card_info.id})
        data = {'device_id': 'TEST_DEVICE'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        card_info.refresh_from_db()
        self.assertTrue(card_info.is_mobile_nfc)
        self.assertEqual(card_info.mobile_device_id, 'TEST_DEVICE')

    def test_generate_virtual_card(self):
        url = reverse('temporaryvirtualcard-generate')
        data = {'passenger_id': self.passenger.id}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('virtual_card', response.data)
        self.assertIn('qr_code', response.data)
        self.assertEqual(TemporaryVirtualCard.objects.count(), 1)

    def test_use_virtual_card(self):
        virtual_card = TemporaryVirtualCard.objects.create(
            passenger=self.passenger,
            qr_code='TEST_QR_CODE',
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )
        url = reverse('temporaryvirtualcard-use-card', kwargs={'pk': virtual_card.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        virtual_card.refresh_from_db()
        self.assertTrue(virtual_card.is_used)

    def test_use_expired_virtual_card(self):
        virtual_card = TemporaryVirtualCard.objects.create(
            passenger=self.passenger,
            qr_code='TEST_QR_CODE',
            expires_at=timezone.now() - timezone.timedelta(hours=1)
        )
        url = reverse('temporaryvirtualcard-use-card', kwargs={'pk': virtual_card.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_card_assignments(self):
        self.create_card_assignment()
        url = reverse('cardassignmentid-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_card_info(self):
        card_assignment = self.create_card_assignment()
        CardInfo.objects.create(
            card_assignment=card_assignment,
            passenger=self.passenger,
            card_type='rfid',
            expiry_date='2025-01-01'
        )
        url = reverse('cardinfo-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_card_info(self):
        card_assignment = self.create_card_assignment()
        card_info = CardInfo.objects.create(
            card_assignment=card_assignment,
            passenger=self.passenger,
            card_type='rfid',
            expiry_date='2025-01-01'
        )
        url = reverse('cardinfo-detail', kwargs={'pk': card_info.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['card_type'], 'rfid')

    def test_update_card_info(self):
        card_assignment = self.create_card_assignment()
        card_info = CardInfo.objects.create(
            card_assignment=card_assignment,
            passenger=self.passenger,
            card_type='rfid',
            expiry_date='2025-01-01'
        )
        url = reverse('cardinfo-detail', kwargs={'pk': card_info.id})
        data = {'expiry_date': '2026-01-01'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        card_info.refresh_from_db()
        self.assertEqual(str(card_info.expiry_date), '2026-01-01')

    def test_delete_card_info(self):
        card_assignment = self.create_card_assignment()
        card_info = CardInfo.objects.create(
            card_assignment=card_assignment,
            passenger=self.passenger,
            card_type='rfid',
            expiry_date='2025-01-01'
        )
        url = reverse('cardinfo-detail', kwargs={'pk': card_info.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(CardInfo.objects.count(), 0)
        
class PaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.force_authenticate(user=self.user)

    def test_process_payment(self):
        url = reverse('payment-process-payment')
        data = {
            'user': self.user.id,
            'amount': 100.00,
            'payment_type': 'top_up'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Balance.objects.get(user=self.user).amount, 100.00)

class BalanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.balance = Balance.objects.create(user=self.user, amount=100.00)
        self.client.force_authenticate(user=self.user)

    def test_update_balance(self):
        url = reverse('balance-update-balance', kwargs={'pk': self.balance.pk})
        data = {
            'amount': '50.00',  # Envoyez le montant en tant que chaîne
            'description': 'Test transaction'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.amount, Decimal('50.00'))
        self.assertEqual(Transaction.objects.count(), 1)
        


class TransportValidationTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Créer un utilisateur unique pour chaque test
        self.user = User.objects.create_user(
            username=f'testuser_{uuid.uuid4()}',
            password='12345'
        )
        
        # Créer un OperationalControlPlan
        self.ocp = OperationalControlPlan.objects.create(
            name="Test OCP",
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=30),
            created_by=self.user
        )
        
        # Utiliser get_or_create pour PassengerUser
        self.passenger, _ = PassengerUser.objects.get_or_create(
            user=self.user,
            defaults={'account_status': 'active'}
        )
        
        self.plan = SubscriptionPlan.objects.create(
            user_type='student',
            circuit='A',
            locality='CentreVille',
            duration='monthly',
            price=100
        )
        
        self.subscription = Subscription.objects.create(
            passenger=self.passenger,
            plan=self.plan,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=30),
            status='active'
        )
        
        # Créer un CardAssignmentid
        self.card_assignment = CardAssignmentid.objects.create(
            user_type=UserType.STUDENT,
            unique_code=f'TEST{uuid.uuid4().hex[:6]}',
            status=Status.ASSIGNED
        )
        
        # Créer un CardInfo avec le CardAssignmentid
        self.card = CardInfo.objects.create(
            passenger=self.passenger,
            card_type='nfc',
            is_active=True,
            nfc_id='test_nfc_id',
            card_assignment=self.card_assignment,
            expiry_date=timezone.now() + timezone.timedelta(days=365),
            issue_date=timezone.now()
        )
        
        # Créer une Route avec l'OCP
        self.route = Route.objects.create(name='Test Route', ocp=self.ocp)
        
        # Créer des Stops
        self.boarding_stop = Stop.objects.create(
            name='Boarding Stop',
            latitude=0,
            longitude=0,
            ocp=self.ocp,
            service_zone='CentreVille',
            circuit='A'
        )
        self.alighting_stop = Stop.objects.create(
            name='Alighting Stop',
            latitude=1,
            longitude=1,
            ocp=self.ocp,
            service_zone='CentreVille',
            circuit='A'
        )
        
        # Associer les stops à la route avec un ordre spécifié
        RouteStop.objects.create(route=self.route, stop=self.boarding_stop, order=1)
        RouteStop.objects.create(route=self.route, stop=self.alighting_stop, order=2)
        
        # Créer un Vehicle
        self.vehicle = Vehicle.objects.create(
            vehicle_number='TEST001',
            capacity=50,
            year=2023
        )
        
        # Créer un Driver
        self.driver = Driver.objects.create(
            user=User.objects.create_user(username=f'testdriver_{uuid.uuid4()}', password='12345'),
            license_number='TEST123',
            experience_years=5,
            ocp=self.ocp
        )
        
        # Créer un Trip
        self.trip = Trip.objects.create(
            route=self.route,
            driver=self.driver,
            vehicle=self.vehicle,
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            ocp=self.ocp  # Assurez-vous que ceci est présent
        )

    def test_boarding_validation_success(self):
        url = reverse('validate_boarding')
        data = {
            'card_data': {
                'card_type': 'physical',
                'card_id': str(self.card.id)
            },
            'trip_id': self.trip.id,
            'stop_id': self.boarding_stop.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['status'], 'boarded')
        self.assertIsNotNone(response.data['boarding_time'])
        self.assertIsNone(response.data['alighting_time'])
        self.assertIsNotNone(response.data['ocp'])  # Ajoutez cette ligne

    def test_boarding_validation_invalid_card(self):
        url = reverse('validate_boarding')
        data = {
            'card_data': {
                'card_type': 'physical',
                'card_id': '999999'  # ID invalide
            },
            'trip_id': self.trip.id,
            'stop_id': self.boarding_stop.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Carte invalide')

    def test_boarding_validation_invalid_subscription(self):
        invalid_stop = Stop.objects.create(
            name='Invalid Stop',
            latitude=2,
            longitude=2,
            ocp=self.ocp,
            service_zone='OtherCity',
            circuit='B'
        )
        RouteStop.objects.create(route=self.route, stop=invalid_stop, order=3)
        url = reverse('validate_boarding')
        data = {
            'card_data': {
                'card_type': 'physical',
                'card_id': str(self.card.id)
            },
            'trip_id': self.trip.id,
            'stop_id': invalid_stop.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Pas d'abonnement valide pour cette localité")

    def test_alighting_validation_success(self):
        passenger_trip = PassengerTrip.objects.create(
            passenger=self.user,
            trip=self.trip,
            boarding_stop=self.boarding_stop,
            alighting_stop=self.alighting_stop,
            ocp=self.ocp,
            status='boarded'
        )

        url = reverse('validate_alighting')
        data = {
            'passenger_trip_id': passenger_trip.id,
            'stop_id': self.alighting_stop.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        self.assertIsNotNone(response.data['alighting_time'])

    def test_alighting_validation_invalid_trip(self):
        url = reverse('validate_alighting')
        data = {
            'passenger_trip_id': 99999,  # ID invalide
            'stop_id': self.alighting_stop.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Trajet passager invalide ou déjà terminé")

    def test_alighting_validation_invalid_stop(self):
        passenger_trip = PassengerTrip.objects.create(
            passenger=self.user,
            trip=self.trip,
            boarding_stop=self.boarding_stop,
            alighting_stop=self.alighting_stop,
            ocp=self.ocp,
            status='boarded'
        )

        url = reverse('validate_alighting')
        data = {
            'passenger_trip_id': passenger_trip.id,
            'stop_id': 99999  # ID invalide
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Arrêt invalide")