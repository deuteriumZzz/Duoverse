"""Tell the other side of a pair that something happened: Telegram when linked, otherwise email."""

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from .models import Pair

MESSAGES = {
    "answered": ("{name} ответил(а) на вопрос дня. Ответьте и вы — и ответы откроются вам обоим.", "daily"),
    "joined": ("{name} присоединился(лась) к вашей паре в Duoverse. Теперь разбор, план и вопрос дня у вас общие.", "history"),
    "quiz": ("{name} прошёл(ла) квиз недели. Пройдите и вы — и увидите, где вы совпадаете.", "quiz_week"),
    "reminder": ("Вопрос дня ждёт вас двоих. Пара минут — и узнаете, что ответил партнёр.", "daily"),
}


def notify_partner(pair: Pair, side: str, event: str) -> None:
    """`side` («a» creator / «b» partner) did `event`; the other side hears about it after the transaction commits."""
    target = pair.partner if side == "a" else pair.owner
    if target is None:
        return
    name = pair.a.name if side == "a" else pair.b.name
    notify(str(target.id), event, name=name)


def notify(owner_id: str, event: str, **fmt: str) -> None:
    from .tasks import deliver

    text, view = MESSAGES[event]
    url = settings.SITE_URL.rstrip("/") + reverse(view)
    transaction.on_commit(lambda: deliver.delay(owner_id, text.format(**fmt), url))
