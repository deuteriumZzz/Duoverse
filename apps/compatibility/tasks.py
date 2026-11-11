import logging

from celery import shared_task

from config.container import report_provider

from .models import StoredReport
from .services import person_input

log = logging.getLogger(__name__)


@shared_task(bind=True, acks_late=True, max_retries=2, default_retry_delay=5)
def generate_report(self, report_id: str) -> str:
    """Idempotent: a ready report is never recalculated; failures are stored for the UI."""
    stored = StoredReport.objects.select_related("pair__a", "pair__b").get(id=report_id)
    if stored.status == StoredReport.Status.READY:
        return report_id
    try:
        report = report_provider().build(report_id, person_input(stored.pair.a), person_input(stored.pair.b))
    except Exception as exc:  # noqa: BLE001 — any failure is surfaced to the user as the error state
        log.exception("report %s failed", report_id)
        if self.request.retries < self.max_retries and not self.request.is_eager:
            raise self.retry(exc=exc) from exc
        stored.status, stored.error = StoredReport.Status.FAILED, f"{type(exc).__name__}: {exc}"
        stored.save(update_fields=["status", "error"])
        return report_id
    stored.snapshot, stored.status = report.model_dump(mode="json"), StoredReport.Status.READY
    stored.save(update_fields=["snapshot", "status"])
    return report_id


@shared_task
def deliver(owner_id: str, text: str, url: str) -> str:
    """One notification: Telegram if the person linked the bot, otherwise a short email."""
    from django.core.mail import send_mail

    from .infrastructure.telegram import send_message
    from .models import Owner

    owner = Owner.objects.filter(id=owner_id).first()
    if owner is None:
        return "gone"
    if owner.telegram_chat_id and send_message(owner.telegram_chat_id, text, url):
        return "telegram"
    if owner.email:
        send_mail("Duoverse", f"{text}\n\n{url}", None, [str(owner.email)])
        return "email"
    return "none"
