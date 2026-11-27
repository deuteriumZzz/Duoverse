"""Tell the other side of a pair that something happened: Telegram when linked, otherwise email."""

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from .models import Pair

MESSAGES = {
    "answered": ("{name} {ответил|ответила|ответил(а)} на вопрос дня. Ответьте и вы, и ответы откроются вам обоим.", "daily"),
    "joined": (
        "{name} {присоединился|присоединилась|присоединился(лась)} к вашей паре в Duoverse. Теперь разбор, план и вопрос дня у вас общие.",
        "history",
    ),
    "quiz": ("{name} {прошёл|прошла|прошёл(ла)} квиз недели. Пройдите и вы, чтобы увидеть, где совпадаете.", "quiz_week"),
    "reminder": ("Вопрос дня ждёт вас двоих. Пара минут, и вы узнаете, что ответил партнёр.", "daily"),
    "invite": (
        "Приглашение в пару ждёт ответа: {name} пока не с вами в Duoverse. "
        "Отправьте ссылку ещё раз — разбор, план и вопрос дня станут общими.",
        "account",
    ),
    "week": ("{name} {начал|начала|начал(а)} «Неделю пары»: семь коротких шагов из вашего разбора. Первый уже сегодня.", "daily"),
    "date": ("{text}", "pair_calendar"),  # built by dates.reminder_text
    # neutral on purpose, whatever the theme: a preview shows on a locked screen, mail is read at work
    "idea": ("Для вас двоих есть идея на эту неделю. Загляните в «Сегодня».", "daily"),
    "nudge": ("{name} думает о вас.", "pair_invite"),
    "thanks": ("{name} говорит вам спасибо — загляните на главную.", "pair_invite"),  # the words stay in the app
    "trial_end": (
        "Подарочная неделя «Пары+» закончится в ближайшие сутки. Закроются квиз недели, дневник ответов, "
        "тихая бронь подарков и план свидания. Дерево, календарь, желания и вопрос дня останутся с вами.",
        "pricing",
    ),
}


def notify_partner(pair: Pair, side: str, event: str) -> None:
    """`side` («a» creator / «b» partner) did `event`; the other side hears about it after the transaction commits."""
    target = pair.partner if side == "a" else pair.owner
    if target is None:
        return
    who = pair.a if side == "a" else pair.b
    notify(str(target.id), event, gender=who.gender, name=who.name)


def notify(owner_id: str, event: str, gender: str = "", **fmt: str) -> None:
    """{ответил|ответила|ответил(а)} in a message becomes the actor's form (names.inflect), neutral if unknown."""
    from apps.core.domain.names import inflect

    from .tasks import deliver

    text, view = MESSAGES[event]
    url = settings.SITE_URL.rstrip("/") + reverse(view)
    transaction.on_commit(lambda: deliver.delay(owner_id, inflect(text, gender).format(**fmt), url))
