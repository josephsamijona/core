from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import Schedule, OperationalControlPlan, Route, Vehicle,DriverVehicleAssignment,Driver
from datetime import time
from django.urls import reverse
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

class OCPTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.force_authenticate(user=self.user)

    def test_create_ocp(self):
        data = {
            'name': 'Test OCP',
            'start_date': timezone.now().isoformat(),
            'end_date': (timezone.now() + timedelta(days=30)).isoformat(),
            'min_drivers_per_shift': 2,
            'min_vehicles_per_shift': 2,
        }
        response = self.client.post('/api/transport/ocps/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OperationalControlPlan.objects.count(), 1)
        self.assertEqual(OperationalControlPlan.objects.get().name, 'Test OCP')

    def test_activate_ocp(self):
        ocp = OperationalControlPlan.objects.create(
            name='Test OCP',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )
        response = self.client.patch(f'/api/transport/ocps/{ocp.id}/activate/', {'is_active': True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ocp.refresh_from_db()
        self.assertTrue(ocp.is_active)

    def test_update_ocp(self):
        ocp = OperationalControlPlan.objects.create(
            name='Test OCP',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )
        new_name = 'Updated OCP'
        response = self.client.patch(f'/api/transport/ocps/{ocp.id}/', {'name': new_name})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ocp.refresh_from_db()
        self.assertEqual(ocp.name, new_name)

    def test_delete_ocp(self):
        ocp = OperationalControlPlan.objects.create(
            name='Test OCP',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )
        response = self.client.delete(f'/api/transport/ocps/{ocp.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(OperationalControlPlan.objects.count(), 0)

    def test_delete_active_ocp(self):
        ocp = OperationalControlPlan.objects.create(
            name='Active OCP',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=self.user,
            is_active=True
        )
        response = self.client.delete(f'/api/transport/ocps/{ocp.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OperationalControlPlan.objects.count(), 1)
        self.assertEqual(response.data['detail'], "Cannot delete an active OCP.")

    def test_auto_renew_ocp(self):
        old_ocp = OperationalControlPlan.objects.create(
            name='Old OCP',
            start_date=timezone.now() - timedelta(days=31),
            end_date=timezone.now() - timedelta(days=1),
            created_by=self.user,
            is_active=True
        )
        response = self.client.get('/api/transport/ocps/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Vérifier qu'un nouvel OCP a été créé
        self.assertEqual(OperationalControlPlan.objects.count(), 2)
        new_ocp = OperationalControlPlan.objects.exclude(pk=old_ocp.pk).first()
        self.assertTrue(new_ocp.is_active)
        self.assertTrue(new_ocp.is_renewed)
        
        old_ocp.refresh_from_db()
        self.assertFalse(old_ocp.is_active)

    def test_activate_future_ocp(self):
        old_ocp = OperationalControlPlan.objects.create(
            name='Old OCP',
            start_date=timezone.now() - timedelta(days=31),
            end_date=timezone.now() - timedelta(days=1),
            created_by=self.user,
            is_active=True
        )
        future_ocp = OperationalControlPlan.objects.create(
            name='Future OCP',
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=31),
            created_by=self.user,
            is_active=False
        )
        response = self.client.get('/api/transport/ocps/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        old_ocp.refresh_from_db()
        future_ocp.refresh_from_db()
        self.assertFalse(old_ocp.is_active)
        self.assertTrue(future_ocp.is_active)
        
        
class ScheduleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.force_authenticate(user=self.user)

        self.ocp = OperationalControlPlan.objects.create(
            name="Test OCP",
            start_date="2023-01-01T00:00:00Z",
            end_date="2023-12-31T23:59:59Z",
            created_by=self.user,
            frequency=30,
            buffer_time_between_trips=5,
            active_days=["monday", "tuesday", "wednesday", "thursday", "friday"]
        )

        self.route = Route.objects.create(
            name="Test Route",
            ocp=self.ocp
        )

    def test_create_schedule(self):
        data = {
            "ocp": self.ocp.id,
            "route": self.route.id,
            "start_time": timezone.now().isoformat(),
            "end_time": (timezone.now() + timezone.timedelta(hours=1)).isoformat(),
            "frequency": 30,
            "day_of_week": "monday"
        }
        response = self.client.post(reverse('schedule-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Schedule.objects.count(), 1)

    def test_generate_schedules(self):
        url = reverse('schedule-generate-schedules')
        data = {"ocp_id": self.ocp.id}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check if schedules were created for each active day
        schedule_count = Schedule.objects.filter(ocp=self.ocp).count()
        expected_count = len(self.ocp.active_days) * ((22 - 6) * 60 // self.ocp.frequency)
        self.assertEqual(schedule_count, expected_count)

    def test_invalid_schedule(self):
        data = {
            "ocp": self.ocp.id,
            "route": self.route.id,
            "start_time": "09:00:00",
            "end_time": "08:00:00",  # Invalid: end time before start time
            "frequency": 30,
            "day_of_week": "monday"
        }
        response = self.client.post(reverse('schedule-list'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_schedule_list(self):
        Schedule.objects.create(
            ocp=self.ocp,
            route=self.route,
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            frequency=30,
            day_of_week="monday"

        )
        response = self.client.get(reverse('schedule-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_schedule_detail(self):
        schedule = Schedule.objects.create(
            ocp=self.ocp,
            route=self.route,
            start_time=timezone.now().replace(hour=8, minute=0, second=0, microsecond=0),
            end_time=timezone.now().replace(hour=9, minute=0, second=0, microsecond=0),
            frequency=30,
            day_of_week="monday"
        )
        response = self.client.get(reverse('schedule-detail', kwargs={'pk': schedule.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['start_time'][:5], '08:00')  # Vérifiez seulement les heures et minutes
        
class ResourceManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.force_authenticate(user=self.user)

        # Créez d'abord un OCP
        self.ocp = OperationalControlPlan.objects.create(
            name="Test OCP",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )
        
        self.route = Route.objects.create(
            name="Test Route",
            ocp=self.ocp
        )
        self.vehicle = Vehicle.objects.create(
            vehicle_number="V001",
            status="operational",
            year=2022
        )

        self.driver = Driver.objects.create(
            user=self.user,
            license_number="D001",
            employment_status="active",
            availability_status="available",
            ocp=self.ocp  # Maintenant, nous pouvons assigner l'OCP au driver
        )

    def test_assign_driver_to_vehicle(self):
        url = reverse('vehicle-assign-driver', kwargs={'pk': self.vehicle.id})
        data = {
            'driver_id': self.driver.id,
            'start_time': timezone.now(),
            'end_time': timezone.now() + timedelta(hours=8)
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DriverVehicleAssignment.objects.count(), 1)

    def test_get_available_vehicles(self):
        url = reverse('driver-available-vehicles', kwargs={'pk': self.driver.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_auto_assign_resources(self):
        # Créez quelques horaires pour aujourd'hui
        today = timezone.now().date()
        Schedule.objects.create(
            ocp=self.ocp,
            route=self.route,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=2),
            frequency=30,
            day_of_week=today.strftime('%A').lower()
        )

        url = reverse('drivervehicleassignment-auto-assign')
        response = self.client.post(url, {'date': today})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Vérifiez qu'une attribution a été créée
        self.assertEqual(DriverVehicleAssignment.objects.count(), 1)