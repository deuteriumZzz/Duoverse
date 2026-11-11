"""Who sees what (ADR-0011): a pair is unlocked by a «deep» purchase for it, or by «Пара+» of either partner."""

from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import Owner, Pair, Purchase


def has_plus(owner: Owner | None) -> bool:
    if owner is None:
        return False
    return Purchase.objects.filter(owner=owner, kind="plus", status="succeeded", valid_until__gt=timezone.now()).exists()


def plus_for_pair(pair: Pair) -> bool:
    """«Пара+» works for both partners of a linked pair."""
    owners = [o for o in (pair.owner, pair.partner) if o is not None]
    return any(has_plus(o) for o in owners)


def unlocked(pair: Pair) -> bool:
    return Purchase.objects.filter(pair=pair, kind="deep", status="succeeded").exists() or plus_for_pair(pair)


def mark_paid(purchase: Purchase) -> None:
    if purchase.status == Purchase.Status.SUCCEEDED:
        return
    purchase.status, purchase.paid_at = Purchase.Status.SUCCEEDED, timezone.now()
    if purchase.kind == "plus":
        # stack on top of an active period so paying early never loses days
        current = (
            Purchase.objects.filter(owner=purchase.owner, kind="plus", status="succeeded", valid_until__gt=timezone.now())
            .exclude(id=purchase.id)
            .order_by("-valid_until")
            .first()
        )
        start = current.valid_until if current and current.valid_until else timezone.now()
        purchase.valid_until = start + timedelta(days=settings.PLUS_DAYS)
    purchase.save(update_fields=["status", "paid_at", "valid_until"])


def purchases_of(owner: Owner):
    return Purchase.objects.filter(Q(owner=owner)).order_by("-created_at")
