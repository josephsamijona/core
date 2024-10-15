# security_management/management/commands/unblock_ips.py
from django.core.management.base import BaseCommand
from security_management.models import BlockedIP
from django.utils import timezone

class Command(BaseCommand):
    help = 'Débloque les IPs dont le blocage a expiré.'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        blocked_ips = BlockedIP.objects.filter(unblock_at__lte=now)

        if blocked_ips.exists():
            count = blocked_ips.count()
            blocked_ips.delete()
            self.stdout.write(self.style.SUCCESS(f"{count} IP(s) débloquées."))
        else:
            self.stdout.write(self.style.SUCCESS("No IPs to unblock."))
