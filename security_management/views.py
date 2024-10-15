# security/views.py
from rest_framework import generics, status
import os
import subprocess
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import SessionManagement, LoginAttempt, BlockedIP
from .serializers import SessionManagementSerializer, LoginAttemptSerializer
import logging
from .tasks import generate_and_send_backup


logger = logging.getLogger(__name__)

class ActiveSessionsView(generics.ListAPIView):
    """Lister toutes les sessions actives de l'utilisateur connecté."""
    serializer_class = SessionManagementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SessionManagement.objects.filter(user=self.request.user, is_active=True)


class TerminateSessionView(generics.DestroyAPIView):
    """Terminer une session spécifique de l'utilisateur."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, session_key, *args, **kwargs):
        try:
            session = SessionManagement.objects.get(session_key=session_key, user=request.user)
            session.end_session()
            return Response({"detail": "Session terminated."}, status=status.HTTP_200_OK)
        except SessionManagement.DoesNotExist:
            return Response({"detail": "Session not found."}, status=status.HTTP_404_NOT_FOUND)


class NotifyNewIPView(generics.GenericAPIView):
    """Notifier l'utilisateur en cas de connexion depuis une nouvelle IP."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        ip_address = request.data.get('ip_address')
        if not ip_address:
            return Response({"detail": "IP address is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        previous_sessions = SessionManagement.objects.filter(user=user, ip_address=ip_address)

        if not previous_sessions.exists():
            # Logique de notification (par exemple, envoi d'un email ou d'une alerte)
            return Response({"detail": "New IP detected, notification sent."}, status=status.HTTP_200_OK)

        return Response({"detail": "IP already known."}, status=status.HTTP_200_OK)

MAX_ATTEMPTS = 5  # Nombre maximal de tentatives avant blocage
BLOCK_DURATION = 60 * 15  # 15 minutes en secondes

class LoginAttemptView(generics.CreateAPIView):
    """Vue pour enregistrer les tentatives de connexion avec blocage automatique."""
    serializer_class = LoginAttemptSerializer

    def post(self, request, *args, **kwargs):
        ip_address = request.data.get('ip_address')
        success = request.data.get('success')

        # Vérifier si l'IP est déjà bloquée
        blocked_ip = BlockedIP.objects.filter(ip_address=ip_address).first()
        if blocked_ip and blocked_ip.is_blocked():
            logger.info(f"IP {ip_address} est déjà bloquée.")
            return Response(
                {"detail": "Cette IP est bloquée."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Enregistrer la tentative
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if not success:
            # Compter les tentatives échouées
            failed_attempts = LoginAttempt.objects.filter(
                ip_address=ip_address, success=False
            ).count()
            logger.info(f"{failed_attempts} tentatives échouées pour l'IP {ip_address}.")

            # Bloquer l'IP si le nombre de tentatives est atteint
            if failed_attempts >= MAX_ATTEMPTS:
                unblock_time = timezone.now() + timezone.timedelta(seconds=BLOCK_DURATION)
                blocked_ip, created = BlockedIP.objects.update_or_create(
                    ip_address=ip_address,
                    defaults={
                        'reason': "Trop de tentatives échouées",
                        'attempt_count': failed_attempts,
                        'unblock_at': unblock_time,
                    }
                )
                if created:
                    logger.info(f"L'IP {ip_address} a été bloquée.")
                else:
                    logger.info(f"L'IP {ip_address} était déjà bloquée.")

                return Response(
                    {"detail": "IP bloquée à cause de trop de tentatives échouées."},
                    status=status.HTTP_403_FORBIDDEN
                )

        logger.info(f"Tentative de connexion pour l'IP {ip_address} réussie.")
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class CreateBackupView(APIView):
    """Vue API pour lancer une sauvegarde manuelle."""
    def post(self, request, *args, **kwargs):
        generate_and_send_backup.delay()  # Exécute la tâche en arrière-plan
        return Response({"detail": "Backup initiated."}, status=200)