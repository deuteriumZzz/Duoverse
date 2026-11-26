"""Hourly housekeeping run by the scheduler container: anonymous data cleanup, the evening reminder and invite nudges."""

import hashlib
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.compatibility import dates, wishes
from apps.compatibility.models import DailyAnswer, Owner, Pair
from apps.compatibility.notify import notify
from apps.compatibility.services import pairs_of, side_of


class Command(BaseCommand):
    help = "Run timed jobs (safe to run every hour)."

    def handle(self, *args, **opts):
        call_command("cleanup_anonymous", days=7)
        now = timezone.localtime()
        if now.hour == settings.REMINDER_HOUR:
            self.remind(now.date())
            self.nudge_invites()
            self.remind_dates(now.date())
            if now.weekday() == 0:
                self.idea_notice(now.date())

    def idea_notice(self, today) -> None:
        """Mondays: both partners of a linked pair hear there's a new «Свидание недели» — never what it is about."""
        year, week, _ = today.isocalendar()
        for pair in Pair.objects.exclude(partner=None).only("owner_id", "partner_id"):
            for owner_id in (pair.owner_id, pair.partner_id):
                if cache.add(f"idea:{owner_id}:{year}-{week}", 1, 8 * 24 * 3600):
                    notify(str(owner_id), "idea")

    def remind_dates(self, today) -> None:
        """A week and a day before each date in the latest pair's calendar; a birthday is told only to the other partner.
        ponytail: walks every account and decrypts its pair daily — fine for thousands, batch by birthday month past that."""
        accounts = Owner.objects.filter(Q(email_hash__isnull=False) | Q(identities__isnull=False)).distinct()
        for owner in accounts:
            pair = pairs_of(owner).select_related("a", "b").order_by("-created_at").first()
            if not pair:
                continue
            side = side_of(owner, pair)
            for event in dates.due(dates.upcoming(today, dates.people(pair), pair.dates, horizon=7)):
                key = hashlib.sha1(f"{event['kind']}|{event['title']}|{event['day']}".encode()).hexdigest()[:12]
                if side in dates.recipients(event) and cache.add(f"date:{owner.id}:{key}:{today}", 1, 26 * 3600):
                    ideas = wishes.ideas_for(pair.wishes, event["side"]) if event["kind"] == "birthday" else None
                    notify(str(owner.id), "date", text=dates.reminder_text(event, ideas))

    def nudge_invites(self) -> None:
        """Once per pair, two days on: the inviter hears that the partner hasn't joined yet, with the way to resend."""
        signed_in = Q(owner__email_hash__isnull=False) | Q(owner__identities__isnull=False)
        stale = Pair.objects.filter(signed_in, partner=None, invite_code__isnull=False, created_at__lt=timezone.now() - timedelta(days=2))
        for pair in stale.select_related("b").distinct():
            if pair.plan.get("invite_nudged"):
                continue
            pair.plan = {**pair.plan, "invite_nudged": True}
            pair.save(update_fields=["plan"])
            notify(str(pair.owner_id), "invite", name=pair.b.name)

    def remind(self, today) -> None:
        """Once a day, people with Telegram linked who haven't answered today's question in a pair with a partner."""
        for owner in Owner.objects.exclude(telegram_chat_id=None):
            pair = pairs_of(owner).exclude(partner=None).order_by("-created_at").first()
            if not pair or DailyAnswer.objects.filter(pair=pair, side=side_of(owner, pair), day=today).exists():
                continue
            if cache.add(f"reminded:{owner.id}:{today}", 1, 26 * 3600):
                notify(str(owner.id), "reminder")
