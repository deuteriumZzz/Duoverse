"""Delete what anonymous devices left behind: data entered without ever signing in, older than N days (152-ФЗ)."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.compatibility.models import Owner


class Command(BaseCommand):
    help = "Delete anonymous owners (no email, no sign-in) older than --days, with their people, pairs and reports."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, days=7, **opts):
        cutoff = timezone.now() - timedelta(days=days)
        stale = Owner.objects.filter(email_hash__isnull=True, identities__isnull=True, created_at__lt=cutoff)
        n = stale.count()
        stale.delete()  # cascades to devices, people, answers, pairs, reports
        self.stdout.write(f"deleted {n} anonymous owners older than {days} days")
