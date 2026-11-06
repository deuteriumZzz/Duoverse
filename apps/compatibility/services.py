"""Application services over the ORM: owners, pairs, stored reports, signed links."""

import hashlib
import json
from datetime import date, time

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from apps.compatibility.application.build_report import PersonInput
from apps.compatibility.domain.report import Report

from .models import Owner, Pair, Person, StoredReport

SALT_OWNER, SALT_SHARE, SALT_INVITE, SALT_MAGIC = "dv.owner", "dv.share", "dv.invite", "dv.magic"


# ── device owner (ADR-0007) ───────────────────────────────────────────────
def get_owner(request: HttpRequest) -> Owner | None:
    raw = request.COOKIES.get(settings.OWNER_COOKIE)
    if not raw:
        return None
    try:
        oid = signing.loads(raw, salt=SALT_OWNER)
    except signing.BadSignature:
        return None
    return Owner.objects.filter(id=oid).first()


def remember_owner(response: HttpResponse, owner: Owner) -> HttpResponse:
    response.set_cookie(
        settings.OWNER_COOKIE,
        signing.dumps(str(owner.id), salt=SALT_OWNER),
        max_age=settings.OWNER_COOKIE_AGE,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
    )
    return response


def forget_owner(response: HttpResponse) -> HttpResponse:
    response.delete_cookie(settings.OWNER_COOKIE)
    return response


# ── people and pairs ─────────────────────────────────────────────────────
def birth_payload(day: date, at: time | None, place: str | None) -> dict:
    return {"date": day.isoformat(), "time": at.strftime("%H:%M") if at else None, "place": place or None}


def person_input(p: Person) -> PersonInput:
    b = p.birth
    return PersonInput(
        str(p.id),
        p.name,
        date.fromisoformat(b["date"]),
        time.fromisoformat(b["time"]) if b.get("time") else None,
        b.get("place"),
        p.answers,
    )


@transaction.atomic
def create_pair(owner: Owner, a: dict, b: dict, mode: str) -> Pair:
    now = timezone.now()
    pa = Person.objects.create(
        owner=owner, name=a["name"] or "Я", birth=birth_payload(a["date"], a.get("time"), a.get("place")), consent_at=now
    )
    pb = Person.objects.create(
        owner=owner, name=b["name"] or "Партнёр", birth=birth_payload(b["date"], b.get("time"), b.get("place")), consent_at=now
    )
    return Pair.objects.create(owner=owner, a=pa, b=pb, mode=mode)


def input_hash(pair: Pair) -> str:
    payload = [{"name": p.name, "birth": p.birth, "answers": p.answers} for p in (pair.a, pair.b)]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def request_report(pair: Pair) -> StoredReport:
    """Reuse a ready snapshot for identical inputs (ADR-0003), otherwise queue a new calculation."""
    from .tasks import generate_report

    h = input_hash(pair)
    existing = StoredReport.objects.filter(
        pair=pair, input_hash=h, algorithm_version=settings.ALGORITHM_VERSION, status=StoredReport.Status.READY
    ).first()
    if existing:
        return existing
    stored = StoredReport.objects.create(pair=pair, input_hash=h, algorithm_version=settings.ALGORITHM_VERSION)
    transaction.on_commit(lambda: generate_report.delay(str(stored.id)))
    return stored


def report_of(stored: StoredReport) -> Report:
    return Report.model_validate(stored.snapshot)


def latest_ready(pair: Pair) -> StoredReport | None:
    return pair.reports.filter(status=StoredReport.Status.READY).first()


# ── signed links ─────────────────────────────────────────────────────────
def share_token(stored: StoredReport) -> str:
    return signing.dumps(str(stored.id), salt=SALT_SHARE)


def from_share_token(token: str) -> StoredReport | None:
    try:
        rid = signing.loads(token, salt=SALT_SHARE, max_age=settings.SHARE_LINK_MAX_AGE)
    except signing.BadSignature:
        return None
    return StoredReport.objects.filter(id=rid, status=StoredReport.Status.READY).first()


def invite_token(person: Person) -> str:
    return signing.dumps(str(person.id), salt=SALT_INVITE)


def from_invite_token(token: str) -> Person | None:
    try:
        pid = signing.loads(token, salt=SALT_INVITE, max_age=60 * 60 * 24 * 14)
    except signing.BadSignature:
        return None
    return Person.objects.filter(id=pid).first()


def magic_token(owner: Owner) -> str:
    return signing.dumps(str(owner.id), salt=SALT_MAGIC)


def from_magic_token(token: str) -> Owner | None:
    try:
        oid = signing.loads(token, salt=SALT_MAGIC, max_age=60 * 60 * 24)
    except signing.BadSignature:
        return None
    return Owner.objects.filter(id=oid).first()
