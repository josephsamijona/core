# security/tests.py
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import SessionManagement,BlockedIP, LoginAttempt
from django.utils import timezone
from django.test import override_settings
from security_management.tasks import generate_and_send_backup
from django.test import TestCase
from django.core import mail
User = get_user_model()

class SessionManagementAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.session = SessionManagement.objects.create(
            user=self.user,
            session_key='testsession123',
            ip_address='192.168.0.1',
            user_agent='TestBrowser'
        )

    def test_list_active_sessions(self):
        """Tester la liste des sessions actives."""
        url = reverse('active-sessions')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_terminate_session(self):
        """Tester la terminaison d'une session."""
        url = reverse('terminate-session', args=[self.session.session_key])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_active)

    def test_notify_new_ip(self):
        """Tester la notification pour une nouvelle IP."""
        url = reverse('notify-new-ip')
        data = {'ip_address': '10.0.0.2'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('New IP detected', response.data['detail'])

class BruteForceProtectionTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.login_attempt_url = reverse('login-attempt')
        self.ip_address = '192.168.0.1'
        self.data = {
            'ip_address': self.ip_address,
            'success': False,
            'user_agent': 'TestBrowser'
        }

    
    def test_unblock_ip_after_duration(self):
        """Tester le déblocage automatique d'une IP."""
        ip_address = '192.168.0.2'
        BlockedIP.objects.create(
            ip_address=ip_address,
            reason='Testing unblock',
            unblock_at=timezone.now() - timezone.timedelta(minutes=1)  # Déjà expiré
        )

        # Exécuter la commande de déblocage
        blocked_ips = BlockedIP.objects.filter(ip_address=ip_address)
        self.assertTrue(blocked_ips.exists())  # Vérifier que l'IP est bloquée avant déblocage

        # Exécuter la commande manuellement
        from django.core.management import call_command
        call_command('unblock_ips')

        # Vérifier que l'IP est bien débloquée
        blocked_ip_exists = BlockedIP.objects.filter(ip_address=ip_address).exists()
        self.assertFalse(blocked_ip_exists)
        


class BackupAPITest(TestCase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_create_backup_and_send_email(self):
        """Tester la sauvegarde et l'envoi d'email."""
        # Appeler directement la tâche Celery
        generate_and_send_backup()

        # Vérifier que l'email a été envoyé
        self.assertEqual(len(mail.outbox), 1, "L'email de sauvegarde n'a pas été envoyé.")
        self.assertIn('Weekly Backup', mail.outbox[0].subject)