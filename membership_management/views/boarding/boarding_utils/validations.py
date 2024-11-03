# views/boarding/utils/validation.py

import json
import datetime
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

# Importations pour la gestion des cartes NFC
from smartcard.System import readers
from smartcard.util import toHexString
from smartcard.Exceptions import CardConnectionException, NoCardException

# Importations pour la capture de la caméra et la détection des QR codes
import cv2
from pyzbar.pyzbar import decode
from PIL import Image

from membership_management.models import (
    CardInfo, PassengerUser, Subscription,
    BoardingValidation, BoardingError
)
from transport_management.models import Trip, TransactionScan
from .device_manager import get_device, ensure_single_active_session
from .sync_manager import store_offline_validation

# ------------------------------
# Fonctions Utilitaires NFC
# ------------------------------

def get_uid(connection):
    get_uid_command = [0xFF, 0xCA, 0x00, 0x00, 0x00]
    try:
        response, sw1, sw2 = connection.transmit(get_uid_command)
        if sw1 == 0x90 and sw2 == 0x00:
            uid = toHexString(response)
            return uid.replace(' ', '').upper()
        else:
            print(f"Erreur lors de la récupération de l'UID : {sw1:02X} {sw2:02X}")
            return None
    except (NoCardException, CardConnectionException) as e:
        print(f"Exception lors de la récupération de l'UID : {e}")
        return None

def read_card():
    try:
        available_readers = readers()
        if not available_readers:
            return {"error": "Aucun lecteur de carte n'a été trouvé. Veuillez brancher un lecteur."}

        reader = available_readers[0]
        connection = reader.createConnection()
        connection.connect()

        uid = get_uid(connection)
        if not uid:
            return {"error": "Impossible de lire l'UID de la carte."}

        card_data = {
            "uid": uid,
            # Ajoutez d'autres données si nécessaire
        }

        return card_data

    except (NoCardException, CardConnectionException) as e:
        return {"error": f"Erreur de connexion au lecteur : {e}"}
    except Exception as e:
        return {"error": f"Erreur inconnue : {e}"}

# ------------------------------
# Fonctions de Validation
# ------------------------------

def validate_nfc_card(card_data):
    """
    Valide une carte NFC en vérifiant l'UID et les informations associées.
    """
    uid = card_data.get('uid')
    if not uid:
        return {"status": "failure", "message": "UID manquant dans les données de la carte."}

    try:
        card_info = CardInfo.objects.get(card_uid=uid)
        passenger = card_info.passenger

        # Vérifier l'abonnement
        if not check_subscription(passenger.id):
            return {"status": "failure", "message": "Abonnement inactif ou expiré."}

        # Vérifications métier supplémentaires
        if not validate_passenger_type(passenger.id):
            return {"status": "failure", "message": "Passager non autorisé."}

        # Si tout est valide
        return {
            "status": "success",
            "message": "Validation réussie.",
            "passenger_id": passenger.id,
            "trip_id": card_data.get('trip_id')
        }

    except ObjectDoesNotExist:
        return {"status": "failure", "message": "Carte non reconnue."}
    except Exception as e:
        handle_validation_exception(e)
        return {"status": "failure", "message": "Erreur lors de la validation de la carte."}

def validate_qr_code(qr_data):
    """
    Valide un code QR en utilisant les données décodées.
    """
    try:
        # Supposons que qr_data est une chaîne JSON
        data = json.loads(qr_data)
        passenger_id = data.get('passenger_id')
        trip_id = data.get('trip_id')

        if not passenger_id or not trip_id:
            return {"status": "failure", "message": "Données QR invalides."}

        # Vérifier l'abonnement
        if not check_subscription(passenger_id):
            return {"status": "failure", "message": "Abonnement inactif ou expiré."}

        # Vérifications métier supplémentaires
        if not validate_passenger_type(passenger_id):
            return {"status": "failure", "message": "Passager non autorisé."}

        # Vérifier les capacités et la séquence des arrêts si nécessaire
        if not check_capacity_limits(trip_id):
            return {"status": "failure", "message": "Capacité maximale atteinte pour ce voyage."}

        # Si tout est valide
        return {
            "status": "success",
            "message": "Validation réussie.",
            "passenger_id": passenger_id,
            "trip_id": trip_id
        }

    except json.JSONDecodeError:
        return {"status": "failure", "message": "Données QR invalides (JSON non valide)."}
    except Exception as e:
        handle_validation_exception(e)
        return {"status": "failure", "message": "Erreur lors de la validation du QR code."}

def decode_qr_data_from_image(image):
    """
    Décoder les données du QR code à partir d'une image OpenCV.
    """
    try:
        decoded_objects = decode(Image.fromarray(image))

        if not decoded_objects:
            print("Aucun QR code détecté dans l'image.")
            return None

        # Nous prenons le premier QR code détecté
        qr_content = decoded_objects[0].data.decode('utf-8')
        return qr_content

    except Exception as e:
        print(f"Erreur lors du décodage du QR code : {e}")
        return None

def capture_and_decode_qr_code():
    """
    Capture des images de la caméra et tente de décoder un QR code.
    """
    try:
        # Initialiser la capture vidéo (0 pour la caméra par défaut)
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("Impossible d'ouvrir la caméra")
            return None

        print("Appuyez sur 'q' pour quitter la capture.")

        while True:
            ret, frame = cap.read()
            if not ret:
                print("Impossible de lire le cadre de la caméra")
                break

            # Convertir l'image en nuances de gris
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Tenter de décoder le QR code
            qr_content = decode_qr_data_from_image(gray)
            if qr_content:
                print(f"QR Code détecté : {qr_content}")
                cap.release()
                cv2.destroyAllWindows()
                return qr_content

            # Afficher le flux vidéo (facultatif)
            cv2.imshow('Capture du QR Code', frame)

            # Quitter si l'utilisateur appuie sur 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        return None

    except Exception as e:
        print(f"Erreur lors de la capture du QR code : {e}")
        return None

def validate_qr_code_from_camera():
    """
    Capture un QR code depuis la caméra et le valide.
    """
    qr_data = capture_and_decode_qr_code()
    if qr_data:
        validation_result = validate_qr_code(qr_data)
        return validation_result
    else:
        return {"status": "failure", "message": "Aucun QR code détecté."}

# ------------------------------
# Vérifications Métier
# ------------------------------

def check_subscription(passenger_id):
    """
    Vérifie si le passager a un abonnement actif.
    """
    try:
        subscriptions = Subscription.objects.filter(
            passenger_id=passenger_id,
            status='active',
            expiration_date__gte=timezone.now()
        )
        return subscriptions.exists()
    except Exception as e:
        handle_validation_exception(e)
        return False

def validate_passenger_type(passenger_id):
    """
    Gère les validations spécifiques pour différents types de passagers.
    """
    try:
        passenger = PassengerUser.objects.get(id=passenger_id)
        # Exemple : vérifier si le passager est banni
        if passenger.is_banned:
            return False
        # Ajouter d'autres vérifications selon le type de passager
        return True
    except Exception as e:
        handle_validation_exception(e)
        return False

def verify_stop_sequence(trip_id, stop_id):
    """
    Vérifie que l'arrêt actuel correspond à la séquence prévue du voyage.
    """
    # Implémentation selon votre logique métier
    return True

def check_capacity_limits(trip_id):
    """
    Vérifie si le voyage n'a pas atteint sa capacité maximale.
    """
    try:
        trip = Trip.objects.get(id=trip_id)
        if trip.current_passenger_count >= trip.capacity:
            return False
        return True
    except Exception as e:
        handle_validation_exception(e)
        return False

# ------------------------------
# Gestion des Erreurs de Validation
# ------------------------------

def handle_validation_exception(exception):
    """
    Gère les exceptions et les erreurs lors des validations.
    """
    print(f"Exception lors de la validation : {exception}")
    # Enregistrer l'erreur dans la base de données
    BoardingError.objects.create(
        error_message=str(exception),
        timestamp=timezone.now()
    )

def log_validation_error(error_info):
    """
    Enregistre les erreurs de validation dans la base de données.
    """
    try:
        BoardingError.objects.create(
            error_message=error_info.get('error_message', 'Erreur inconnue'),
            additional_info=error_info.get('additional_info', ''),
            timestamp=timezone.now()
        )
    except Exception as e:
        print(f"Erreur lors de l'enregistrement de l'erreur de validation : {e}")

# ------------------------------
# Gestion des Doublons et Validations Hors-ligne
# ------------------------------

def is_duplicate_scan(passenger_id, trip_id, scan_time):
    """
    Vérifie si un scan est un doublon en fonction de l'utilisateur, du voyage et du temps du scan.
    """
    time_threshold = scan_time - datetime.timedelta(minutes=5)
    return TransactionScan.objects.filter(
        passenger_id=passenger_id,
        trip_id=trip_id,
        timestamp__gte=time_threshold
    ).exists()

def store_offline_validation(data):
    """
    Stocke les validations effectuées en mode hors-ligne.
    """
    # Implémentation pour stocker les données hors-ligne
    pass

def sync_offline_validations():
    """
    Synchronise les validations stockées hors-ligne avec la base de données principale.
    """
    # Implémentation de la synchronisation
    pass

# ------------------------------
# Fonction Principale de Validation
# ------------------------------

def main_validation():
    """
    Fonction principale pour lancer la validation via NFC ou QR code.
    """
    print("Sélectionnez le mode de validation :")
    print("1. Validation NFC")
    print("2. Validation QR Code via Caméra")
    choice = input("Votre choix (1/2) : ")

    if choice == '1':
        print("Veuillez présenter votre carte NFC...")
        card_data = read_card()
        if 'error' in card_data:
            print(card_data['error'])
            return
        else:
            # Ajoutez le trip_id si nécessaire
            card_data['trip_id'] = input("Entrez l'ID du voyage : ")
            result = validate_nfc_card(card_data)
            print(result['message'])
    elif choice == '2':
        print("Ouverture de la caméra pour la capture du QR code...")
        result = validate_qr_code_from_camera()
        print(result['message'])
    else:
        print("Choix invalide.")

if __name__ == "__main__":
    main_validation()
