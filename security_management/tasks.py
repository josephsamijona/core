import os
import subprocess
import sqlite3
import csv
import zipfile
import logging
from celery import shared_task
from django.utils import timezone
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import BackupLog

logger = logging.getLogger(__name__)  # Logger pour débogage
User = get_user_model()

# Créer un répertoire de sauvegarde si nécessaire
BACKUP_DIR = os.path.join(settings.BASE_DIR, "backups/")
os.makedirs(BACKUP_DIR, exist_ok=True)

@shared_task
def generate_and_send_backup():
    """Tâche Celery pour générer des sauvegardes et envoyer un email aux administrateurs."""
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    zip_file = f"{BACKUP_DIR}backup_{timestamp}.zip"

    # Initialiser un log de sauvegarde
    backup_log = BackupLog.objects.create(backup_type='Weekly', status='failed')

    try:
        # Chemins des fichiers
        mysql_dump_file = f"{BACKUP_DIR}mysql_backup_{timestamp}.sql"
        sqlite_file = f"{BACKUP_DIR}backup_{timestamp}.sqlite3"
        csv_file = f"{BACKUP_DIR}backup_{timestamp}.csv"

        # Charger le mot de passe MySQL depuis les settings
        mysql_password = settings.MYSQL_PASSWORD

        # 1. Sauvegarde MySQL
        mysql_command = (
            f'mysqldump -u root -p{mysql_password} --all-databases > "{mysql_dump_file}"'
        )
        subprocess.run(mysql_command, shell=True, check=True)

        # 2. Générer une base SQLite vide
        sqlite_conn = sqlite3.connect(sqlite_file)
        sqlite_conn.close()

        # 3. Générer un fichier CSV avec des données d’exemple
        with open(csv_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['ID', 'Name', 'Email'])
            writer.writerow([1, 'John Doe', 'john@example.com'])

        # 4. Créer un fichier ZIP avec toutes les sauvegardes
        with zipfile.ZipFile(zip_file, 'w') as backup_zip:
            backup_zip.write(mysql_dump_file, os.path.basename(mysql_dump_file))
            backup_zip.write(sqlite_file, os.path.basename(sqlite_file))
            backup_zip.write(csv_file, os.path.basename(csv_file))

        # Mise à jour du BackupLog en "success"
        backup_log.status = 'success'
        backup_log.file_path = zip_file
        backup_log.completed_at = timezone.now()
        backup_log.save()

        # Récupérer les emails des administrateurs
        admin_emails = User.objects.filter(user_type='admin').values_list('email', flat=True)

        # Envoyer l'email avec le fichier ZIP en pièce jointe
        email = EmailMessage(
            subject=f"Weekly Backup - {timestamp}",
            body="Veuillez trouver ci-joint les fichiers de sauvegarde.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=list(admin_emails),
        )
        email.attach_file(zip_file)
        email.send()

        logger.info("Backup email sent successfully.")

    except subprocess.CalledProcessError as e:
        logger.error(f"MySQL dump failed: {str(e)}")
        backup_log.status = 'failed'
        backup_log.save()
        raise e

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        backup_log.status = 'failed'
        backup_log.save()
        raise e

    finally:
        # Nettoyer les fichiers temporaires
        for file in [mysql_dump_file, sqlite_file, csv_file]:
            if os.path.exists(file):
                os.remove(file)
                logger.info(f"Deleted temporary file: {file}")
