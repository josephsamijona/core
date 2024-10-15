from django.shortcuts import render
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAdminUser
# Create your views here.
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import User, UserLog , DeviceInfo, Notification

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from rest_framework_simplejwt.tokens import RefreshToken
from .notification_service import NotificationService
from .serializers import UserRegistrationSerializer, LoginSerializer, ChildAccessSerializer, ProfileUpdateSerializer, PasswordResetConfirmSerializer,PasswordResetSerializer
import json

@csrf_exempt
def service_disruption_webhook(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        affected_users = User.objects.filter(subscribed_routes__contains=data['affected_route'])
        for user in affected_users:
            NotificationService.create_notification(
                user=user,
                notification_type='service_disruption',
                message=f"Perturbation sur la ligne {data['affected_route']} : {data['message']}",
                priority='high'
            )
        return HttpResponse(status=200)
    return HttpResponse(status=405)





class UserRegistrationView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {"message": f"{user.get_user_type_display()} enregistré avec succès."},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    
class LoginView(TokenObtainPairView):
    """
    Vue de connexion personnalisée avec gestion des appareils et enfants.
    """
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            username = request.data.get('username')
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response(
                    {"detail": "Utilisateur non trouvé."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Ajouter les enfants si l'utilisateur est un parent
            enfants = []
            if user.user_type == 'parent':
                enfants = [
                    {"id": enfant.user.id, "name": enfant.user.first_name} 
                    for enfant in user.enfants.all()
                ]
            response.data['enfants'] = enfants

        return response

class ChildAccessView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = ChildAccessSerializer(data=request.data)
        if serializer.is_valid():
            child = serializer.validated_data['child']
            tokens = serializer.get_tokens(child.user)
            return Response(tokens, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"detail": "Token de rafraîchissement manquant."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            token = RefreshToken(refresh_token)
            token.blacklist()  # Révoquer le token
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
class PasswordResetView(APIView):
    """
    Vue pour demander la réinitialisation du mot de passe.
    """
    def post(self, request, *args, **kwargs):
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Email de réinitialisation envoyé."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    """
    Vue pour confirmer le changement de mot de passe.
    """
    def post(self, request, uidb64, token, *args, **kwargs):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(uid=uidb64, token=token)
            return Response(
                {"detail": "Mot de passe réinitialisé avec succès."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        serializer = ProfileUpdateSerializer(
            instance=request.user, 
            data=request.data, 
            partial=True, 
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Profil mis à jour avec succès."}, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    



class IsDriverPermission(BasePermission):
    """Permission personnalisée : Vérifie si l'utilisateur est un chauffeur."""
    def has_permission(self, request, view):
        return request.user.user_type == 'driver'

class VehicleInfoView(APIView):
    permission_classes = [IsAuthenticated, IsDriverPermission]

    def get(self, request):
        """Retourne les informations des véhicules pour les chauffeurs."""
        return Response({"detail": "Voici les informations des véhicules."}, status=status.HTTP_200_OK)

class SuspendUserView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            user.is_active = False
            user.save()

            # Journalisation de la suspension
            from user_management.models import UserLog
            UserLog.objects.create(
                user=user,
                action="Suspension de compte",
                ip_address=self.get_client_ip(request),
                details=f"L'utilisateur {user.username} a été suspendu."
            )

            return Response({"detail": "Utilisateur suspendu avec succès."}, status=200)
        except User.DoesNotExist:
            return Response({"detail": "Utilisateur non trouvé."}, status=404)

    @staticmethod
    def get_client_ip(request):
        """Récupère l'adresse IP du client."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    

class DeviceListView(APIView):
    """Vue pour lister les appareils d'un utilisateur."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = DeviceInfo.objects.filter(user=request.user)
        data = [
            {
                "device_name": device.device_name,
                "device_type": device.device_type,
                "last_login": device.last_login
            }
            for device in devices
        ]
        return Response(data, status=200)

class LogoutDeviceView(APIView):
    """Vue pour déconnecter un appareil spécifique à distance."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        device_name = request.data.get('device_name')
        try:
            device = DeviceInfo.objects.get(user=request.user, device_name=device_name)
            device.delete()  # Supprimer l’appareil pour le déconnecter
            UserLog.objects.create(
                user=request.user,
                action="Déconnexion à distance",
                ip_address=self.get_client_ip(request),
                details=f"L'utilisateur a déconnecté l'appareil {device_name}."
            )
            return Response({"detail": "Appareil déconnecté avec succès."}, status=200)
        except DeviceInfo.DoesNotExist:
            return Response({"detail": "Appareil non trouvé."}, status=404)

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
    
class SendNotificationView(APIView):
    """Vue pour envoyer des notifications aux utilisateurs."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        user_ids = request.data.get('user_ids', [])
        message = request.data.get('message', '')
        priority = request.data.get('priority', 'medium')

        users = User.objects.filter(id__in=user_ids)
        notifications = [
            Notification(user=user, message=message, priority=priority, notification_type='promo_offer')
            for user in users
        ]
        Notification.objects.bulk_create(notifications)

        return Response({"detail": "Notifications envoyées avec succès."}, status=201)