"""Hourly housekeeping run by the scheduler container: anonymous data cleanup and the evening reminder."""

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.compatibility.models import DailyAnswer, Owner
from apps.compatibility.notify import notify
from apps.compatibility.services import pairs_of, side_of


class Command(BaseCommand):
    help = "Run timed jobs (safe to run every hour)."

    def handle(self, *args, **opts):
        call_command("cleanup_anonymous", days=7)
        now = timezone.localtime()
        if now.hour == settings.REMINDER_HOUR:
            self.remind(now.date())

    def remind(self, today) -> None:
        """Once a day, people with Telegram linked who haven't answered today's question in a pair with a partner."""
        for owner in Owner.objects.exclude(telegram_chat_id=None):
            pair = pairs_of(owner).exclude(partner=None).order_by("-created_at").first()
            if not pair or DailyAnswer.objects.filter(pair=pair, side=side_of(owner, pair), day=today).exists():
                continue
            if cache.add(f"reminded:{owner.id}:{today}", 1, 26 * 3600):
                notify(str(owner.id), "reminder")
