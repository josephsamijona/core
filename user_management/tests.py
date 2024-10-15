from rest_framework.test import APITestCase
from django.urls import reverse
from rest_framework import status
from .models import User, Eleve, UserLog, DeviceInfo
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response


class UserRegistrationTestCase(APITestCase):

    def test_register_student(self):
        """Test de l'inscription d'un étudiant"""
        url = reverse('user-register')
        data = {
            "email": "student@example.com",
            "password": "Test1234!",
            "password_confirm": "Test1234!",
            "first_name": "Student",
            "last_name": "User",
            "user_type": "etudiant"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(user_type='etudiant').count(), 1)

    def test_register_parent_with_children(self):
        """Test de l'inscription d'un parent avec un enfant"""
        # Création préalable d'un étudiant
        student_user = User.objects.create_user(
            username="child123", email="child@example.com", password="Test1234!", user_type="etudiant"
        )
        Eleve.objects.create(user=student_user, numero_etudiant="12345", classe="Classe A")

        # Inscription du parent avec l'étudiant associé
        url = reverse('user-register')
        data = {
            "email": "parent@example.com",
            "password": "Test1234!",
            "password_confirm": "Test1234!",
            "first_name": "Parent",
            "last_name": "User",
            "user_type": "parent",
            "enfants": ["12345"]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Eleve.objects.filter(parent__email="parent@example.com").count(), 1)

    def test_register_employee(self):
        """Test de l'inscription d'un employé"""
        url = reverse('user-register')
        data = {
            "email": "employee@example.com",
            "password": "Test1234!",
            "password_confirm": "Test1234!",
            "first_name": "Employee",
            "last_name": "User",
            "user_type": "employee"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(user_type='employee').count(), 1)

    def test_register_invalid_user_type(self):
        """Test avec un type d'utilisateur invalide"""
        url = reverse('user-register')
        data = {
            "email": "invaliduser@example.com",
            "password": "Test1234!",
            "password_confirm": "Test1234!",
            "first_name": "Invalid",
            "last_name": "User",
            "user_type": "invalid_type"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('user_type', response.data)

    def test_password_mismatch(self):
        """Test avec des mots de passe non correspondants"""
        url = reverse('user-register')
        data = {
            "email": "mismatch@example.com",
            "password": "Test1234!",
            "password_confirm": "Test5678!",
            "first_name": "Mismatch",
            "last_name": "User",
            "user_type": "etudiant"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

class AuthenticationTestCase(APITestCase):

    def setUp(self):
        """Initialisation des utilisateurs et des URLs."""
        self.parent = User.objects.create_user(
            username="parent_user",
            email="parent@example.com",
            password="Test1234!",
            user_type="parent"
        )
        self.child = User.objects.create_user(
            username="child_user",
            email="child@example.com",
            password="Test1234!",
            user_type="etudiant"
        )
        Eleve.objects.create(user=self.child, parent=self.parent)

        # URLs de l'API
        self.login_url = reverse('token_obtain_pair')
        self.child_access_url = reverse('child-access')
        self.refresh_url = reverse('token_refresh')
        self.logout_url = reverse('logout')

    def test_login_success(self):
        """Test de connexion avec succès."""
        data = {
            "username": "parent_user",
            "password": "Test1234!",
            "device_name": "iPhone",
            "device_type": "mobile"
        }
        response = self.client.post(self.login_url, data, format='json')
        print("Login Response:", response.data)  # Debugging

        self.assertEqual(response.status_code, status.HTTP_200_OK, "Login failed.")
        self.assertIn('access', response.data, "Access token is missing.")
        self.assertIn('refresh', response.data, "Refresh token is missing.")

    def test_child_access(self):
        """Test de génération de token pour un enfant."""
        data = {"child_id": self.child.id}
        response = self.client.post(self.child_access_url, data, format='json')
        print("Child Access Response:", response.data)  # Debugging

        self.assertEqual(response.status_code, status.HTTP_200_OK, "Child access failed.")
        self.assertIn('access', response.data, "Access token is missing.")
        self.assertIn('refresh', response.data, "Refresh token is missing.")

    def test_refresh_token(self):
        """Test de rafraîchissement du token d'accès."""
        data = {
            "username": "parent_user",
            "password": "Test1234!",
            "device_name": "iPhone",
            "device_type": "mobile"
        }
        response = self.client.post(self.login_url, data, format='json')
        refresh_token = response.data.get('refresh')
        self.assertIsNotNone(refresh_token, "Refresh token is missing.")

        response = self.client.post(self.refresh_url, {"refresh": refresh_token}, format='json')
        print("Refresh Token Response:", response.data)  # Debugging

        self.assertEqual(response.status_code, status.HTTP_200_OK, "Token refresh failed.")
        self.assertIn('access', response.data)

    def test_logout(self):
        """Test de déconnexion réussie."""
        data = {
            "username": "parent_user",
            "password": "Test1234!",
            "device_name": "iPhone",
            "device_type": "mobile"
        }
        response = self.client.post(self.login_url, data, format='json')
        refresh_token = response.data.get('refresh')
        self.assertIsNotNone(refresh_token, "Refresh token is missing.")

        response = self.client.post(self.logout_url, {"refresh": refresh_token}, format='json')
        print("Logout Response Status:", response.status_code)  # Debugging

        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT, "Logout failed.")

        response = self.client.post(self.refresh_url, {"refresh": refresh_token}, format='json')
        print("Post-Logout Refresh Response:", response.status_code)  # Debugging

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, "Token should be revoked.")
        
        
class PasswordResetTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='Test1234!'
        )
        self.reset_url = reverse('password_reset')

    def test_password_reset_request(self):
        """Test de la demande de réinitialisation du mot de passe."""
        data = {"email": "test@example.com"}
        response = self.client.post(self.reset_url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], "Email de réinitialisation envoyé.")

    def test_password_reset_confirm(self):
        """Test de la confirmation du mot de passe."""
        token = PasswordResetTokenGenerator().make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        confirm_url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        data = {"new_password": "NewTest1234!", "confirm_password": "NewTest1234!"}
        response = self.client.post(confirm_url, data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], "Mot de passe réinitialisé avec succès.")
        
class ProfileUpdateTestCase(APITestCase):

    def setUp(self):
        """Initialisation des utilisateurs et des URLs."""
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='Test1234!',
            telephone='123456789'
        )
        self.profile_update_url = reverse('profile_update')

    def test_update_profile(self):
        """Test de la mise à jour du profil."""
        self.client.force_authenticate(user=self.user)
        data = {
            'first_name': 'NewFirstName',
            'last_name': 'NewLastName',
            'email': 'newemail@example.com',
            'telephone': '987654321',
            'address': 'New Address'
        }
        response = self.client.put(self.profile_update_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'NewFirstName')
        self.assertEqual(self.user.email, 'newemail@example.com')
        self.assertEqual(self.user.telephone, '987654321')

        # Vérification de la journalisation
        log = UserLog.objects.filter(user=self.user, action="Mise à jour du profil").first()
        self.assertIsNotNone(log)
        self.assertIn("email", log.details)
        self.assertIn("telephone", log.details)
        self.assertEqual(log.ip_address, '127.0.0.1')  # IP par défaut du test
        


class IsDriverPermission(BasePermission):
    """Permission personnalisée : Vérifie si l'utilisateur est un chauffeur."""
    def has_permission(self, request, view):
        return request.user.user_type == 'driver'

class VehicleInfoView(APIView):
    permission_classes = [IsAuthenticated, IsDriverPermission]

    def get(self, request):
        """Retourne les informations des véhicules pour les chauffeurs."""
        return Response({"detail": "Voici les informations des véhicules."}, status=status.HTTP_200_OK)

class DeviceManagementTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='Test1234!'
        )
        DeviceInfo.objects.create(user=self.user, device_name='Phone', device_type='Mobile')

    def test_list_devices(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('device-list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_logout_device(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('device-logout'), {'device_name': 'Phone'})
        self.assertEqual(response.status_code, 200)

class NotificationTestCase(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username='adminuser', email='admin@example.com', password='admin123', is_staff=True
        )
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='Test1234!'
        )

    def test_send_notifications(self):
        self.client.force_authenticate(user=self.admin)
        data = {
            'user_ids': [self.user.id],
            'message': 'Nouvelle promotion disponible !',
            'priority': 'high'
        }
        response = self.client.post(reverse('send-notification'), data, format='json')
        self.assertEqual(response.status_code, 201)
