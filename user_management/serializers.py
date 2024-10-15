from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Eleve, DeviceInfo, UserLog
from django.utils.timezone import now
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    enfants = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )  # Optionnel pour les parents

    class Meta:
        model = User
        fields = ['email', 'password', 'password_confirm', 'first_name', 
                  'last_name', 'user_type', 'enfants']

    def validate(self, attrs):
        """Valide les données d'inscription"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas."})

        if attrs['user_type'] not in ['parent', 'etudiant', 'employee', 'driver', 'admin']:
            raise serializers.ValidationError({"user_type": "Type d'utilisateur invalide."})

        if attrs['user_type'] == 'parent' and not attrs.get('enfants'):
            raise serializers.ValidationError({"enfants": "Un parent doit avoir au moins un enfant."})

        return attrs

    def create(self, validated_data):
        """Créer un utilisateur et gérer les relations parent-enfant si nécessaire"""
        enfants_data = validated_data.pop('enfants', [])
        validated_data.pop('password_confirm')

        # Générer un username à partir de l'email
        username = validated_data['email'].split('@')[0]

        # Création de l'utilisateur
        user = User.objects.create_user(
            username=username,
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            user_type=validated_data['user_type']
        )

        # Associer les enfants au parent si applicable
        if user.user_type == 'parent':
            for enfant_num in enfants_data:
                try:
                    enfant = Eleve.objects.get(numero_etudiant=enfant_num).user
                    enfant.eleve.parent = user
                    enfant.eleve.save()
                except Eleve.DoesNotExist:
                    raise serializers.ValidationError(
                        {"enfants": f"L'étudiant avec le numéro {enfant_num} n'existe pas."}
                    )

        return user
    
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)  # Utilisation de username
    password = serializers.CharField(write_only=True)
    device_name = serializers.CharField(required=True)
    device_type = serializers.CharField(required=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        device_name = attrs.get('device_name')
        device_type = attrs.get('device_type')

        # Vérifier que l'utilisateur existe avec le username fourni
        try:
            user_obj = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"detail": "Utilisateur non trouvé avec ce nom d'utilisateur."}
            )

        # Authentification de l'utilisateur avec username et password
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError(
                {"detail": "Nom d'utilisateur ou mot de passe incorrect."}
            )

        # Vérifier si l'utilisateur est actif
        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "Ce compte utilisateur est désactivé."}
            )

        # Journalisation de l'appareil
        device, created = DeviceInfo.objects.get_or_create(
            user=user, device_name=device_name, device_type=device_type
        )
        device.last_login = now()
        device.save()

        if created:
            print(f"Nouvel appareil détecté : {device_name} ({device_type})")

        attrs['user'] = user
        return attrs

    def get_tokens(self, user):
        """Génère et retourne les tokens JWT pour l'utilisateur."""
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

class ChildAccessSerializer(serializers.Serializer):
    child_id = serializers.IntegerField()

    def validate(self, attrs):
        """Valide l'accès à un enfant spécifique."""
        child_id = attrs.get('child_id')
        try:
            child = Eleve.objects.get(user__id=child_id)
        except Eleve.DoesNotExist:
            raise serializers.ValidationError(
                {"detail": "L'enfant sélectionné n'existe pas."}
            )
        attrs['child'] = child
        return attrs

    def get_tokens(self, child_user):
        """Génère et retourne les tokens JWT pour l'utilisateur enfant."""
        refresh = RefreshToken.for_user(child_user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, attrs):
        email = attrs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": "Aucun utilisateur trouvé avec cet email."})

        self.context['user'] = user
        return attrs

    def save(self):
        user = self.context['user']
        token = PasswordResetTokenGenerator().make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_url = f"http://localhost:8000/password-reset-confirm/{uid}/{token}/"
        
        # Envoi de l'e-mail avec le lien de réinitialisation
        user.email_user(
            subject="Réinitialisation de votre mot de passe",
            message=f"Cliquez sur ce lien pour réinitialiser votre mot de passe : {reset_url}",
        )

class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"detail": "Les mots de passe ne correspondent pas."})
        return attrs

    def save(self, uid, token):
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError({"detail": "Lien de réinitialisation invalide."})

        if not PasswordResetTokenGenerator().check_token(user, token):
            raise serializers.ValidationError({"detail": "Le lien de réinitialisation a expiré ou est invalide."})

        # Modifier le mot de passe et sauvegarder l'utilisateur
        user.set_password(self.validated_data['new_password'])
        user.save()


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 
            'telephone', 'address', 'date_of_birth', 'sex'
        ]

    def validate_email(self, value):
        """Validation de l'unicité de l'email."""
        user = self.context['request'].user
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé par un autre utilisateur.")
        return value

    def update(self, instance, validated_data):
        """Mise à jour des informations de profil avec journalisation."""
        request = self.context.get('request')  # Extraction du request pour l'IP
        modified_fields = []

        # Mise à jour des champs du profil
        for field, value in validated_data.items():
            old_value = getattr(instance, field)
            if old_value != value:  # Vérifie si le champ a changé
                setattr(instance, field, value)
                modified_fields.append(f"{field}: '{old_value}' -> '{value}'")

        instance.save()

        # Journalisation de l'action avec les champs modifiés
        if modified_fields:
            UserLog.objects.create(
                user=instance,
                action="Mise à jour du profil",
                ip_address=self.get_client_ip(request),
                details=f"Champs modifiés : {', '.join(modified_fields)}"
            )

        return instance

    @staticmethod
    def get_client_ip(request):
        """Récupère l'adresse IP du client à partir du request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip