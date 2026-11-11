"""Register the bot webhook: manage.py telegram_setup (needs TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, SITE_URL)."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from apps.compatibility.infrastructure.telegram import call


class Command(BaseCommand):
    help = "Point the Telegram bot at this site's webhook."

    def handle(self, *args, **opts):
        if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_WEBHOOK_SECRET and settings.SITE_URL.startswith("https://")):
            raise CommandError("Set TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET and an https SITE_URL first")
        url = settings.SITE_URL.rstrip("/") + reverse("telegram_webhook", args=[settings.TELEGRAM_WEBHOOK_SECRET])
        result = call("setWebhook", {"url": url, "secret_token": settings.TELEGRAM_WEBHOOK_SECRET, "allowed_updates": ["message"]})
        self.stdout.write(str(result))
