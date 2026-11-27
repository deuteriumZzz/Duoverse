"""Who sees what (ADR-0011): a pair's full report opens by a «deep» purchase for it, or by a paid year of «Пара+» of
either partner. Any «Пара+» (month, year, the free week) opens the daily extras: quiz, diary, quiet reservation, date plan."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Owner, Pair, Purchase

PLUS_DAYS = {"plus": settings.PLUS_DAYS, "plus365": 365, "trial": settings.PLUS_TRIAL_DAYS}  # every kind that is «Пара+»


def has_plus(owner: Owner | None) -> bool:
    if owner is None:
        return False
    return Purchase.objects.filter(owner=owner, kind__in=PLUS_DAYS, status="succeeded", valid_until__gt=timezone.now()).exists()


def plus_until(owner: Owner):
    return (
        Purchase.objects.filter(owner=owner, kind__in=PLUS_DAYS, status="succeeded", valid_until__gt=timezone.now())
        .order_by("-valid_until")
        .values_list("valid_until", flat=True)
        .first()
    )


def shared_plus_until(owner: Owner | None):
    """When «Пара+» ends for this person — their own or a partner's: it works for both, so the badge, the profile and
    the plans must say so too (Миша sees «Пара+» that Аня paid for). None when there's none."""
    if owner is None:
        return None
    paired = Pair.objects.filter(Q(owner=owner) | Q(partner=owner)).values_list("owner_id", "partner_id")
    ids = {owner.id} | {i for row in paired for i in row if i}
    return (
        Purchase.objects.filter(owner_id__in=ids, kind__in=PLUS_DAYS, status="succeeded", valid_until__gt=timezone.now())
        .order_by("-valid_until")
        .values_list("valid_until", flat=True)
        .first()
    )


def plus_for_pair(pair: Pair) -> bool:
    """«Пара+» works for both partners of a linked pair."""
    owners = [o for o in (pair.owner, pair.partner) if o is not None]
    return any(has_plus(o) for o in owners)


def year_for_pair(pair: Pair) -> bool:
    """A paid year of «Пара+» of either partner also opens all their reports; the month and the free week don't, so 249 ₽
    never undercuts the 490 ₽ report and the week never gives the report away."""
    owners = [o for o in (pair.owner, pair.partner) if o is not None]
    return Purchase.objects.filter(owner__in=owners, kind="plus365", status="succeeded", valid_until__gt=timezone.now()).exists()


def unlocked(pair: Pair) -> bool:
    return Purchase.objects.filter(pair=pair, kind="deep", status="succeeded").exists() or year_for_pair(pair)


def mark_paid(purchase: Purchase) -> None:
    if purchase.status == Purchase.Status.SUCCEEDED:
        return
    purchase.status, purchase.paid_at = Purchase.Status.SUCCEEDED, timezone.now()
    if purchase.kind in PLUS_DAYS:
        # stack on top of the pair's active period (yours or your partner's) so paying early never loses days
        start = shared_plus_until(purchase.owner) or timezone.now()
        purchase.valid_until = start + timedelta(days=PLUS_DAYS[purchase.kind])
    if purchase.kind == "gift":
        purchase.gift_code = new_gift_code()
    purchase.save(update_fields=["status", "paid_at", "valid_until", "gift_code"])


GIFT_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I — easy to read aloud


def new_gift_code() -> str:
    while True:
        code = "".join(secrets.choice(GIFT_ALPHABET) for _ in range(8))
        if not Purchase.objects.filter(gift_code=code).exists():
            return code


def open_gift(code: str) -> Purchase | None:
    """A paid gift that nobody has used yet."""
    code = code.strip().upper().replace("-", "")
    return Purchase.objects.filter(kind="gift", status="succeeded", gift_code=code, pair__isnull=True).first() if code else None


@transaction.atomic
def redeem_gift(gift: Purchase, pair: Pair, owner: Owner) -> None:
    """The gift becomes a full report for this pair (both partners see it); the gift remembers where it went."""
    gift = Purchase.objects.select_for_update().get(id=gift.id)
    if gift.pair_id:
        return
    now = timezone.now()
    Purchase.objects.create(owner=owner, pair=pair, kind="deep", amount=0, status=Purchase.Status.SUCCEEDED, paid_at=now)
    gift.pair = pair
    gift.save(update_fields=["pair"])


def grant_trial(pair: Pair) -> bool:
    """A week of «Пара+» when a partner first joins — the moment both see what the pair gets. Once per inviter, ever."""
    if pair.owner is None or Purchase.objects.filter(owner=pair.owner, kind="trial").exists():
        return False
    now = timezone.now()
    Purchase.objects.create(
        owner=pair.owner, pair=pair, kind="trial", amount=0, status=Purchase.Status.SUCCEEDED, paid_at=now,
        valid_until=now + timedelta(days=PLUS_DAYS["trial"]),
    )  # fmt: skip
    return True


def purchases_of(owner: Owner):
    return Purchase.objects.filter(Q(owner=owner)).order_by("-created_at")
