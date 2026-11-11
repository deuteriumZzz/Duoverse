"""Application services over the ORM: owners, pairs, stored reports, signed links."""

import hashlib
import hmac
import json
import secrets
from datetime import date, time, timedelta

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import models, transaction
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from apps.compatibility.application.build_report import PersonInput
from apps.compatibility.domain.report import Report

from .models import Device, Identity, Owner, Pair, Person, StoredReport

SALT_DEVICE, SALT_SHARE, SALT_LOGIN = "dv.device", "dv.share", "dv.login"


# ── devices and accounts (ADR-0007, ADR-0010) ──────────────────────────────
def get_device(request: HttpRequest) -> Device | None:
    if not hasattr(request, "_dv_device"):
        device = None
        raw = request.COOKIES.get(settings.OWNER_COOKIE)
        try:
            did = signing.loads(raw, salt=SALT_DEVICE) if raw else None
        except signing.BadSignature:
            did = None
        if did:
            device = Device.objects.select_related("owner").filter(id=did).first()
            if device and timezone.now() - device.last_seen_at > timedelta(hours=1):
                Device.objects.filter(id=device.id).update(last_seen_at=timezone.now())
        request._dv_device = device  # type: ignore[attr-defined]
    return request._dv_device  # type: ignore[attr-defined]


def get_owner(request: HttpRequest) -> Owner | None:
    device = get_device(request)
    return device.owner if device else None


def remember_owner(request: HttpRequest, response: HttpResponse, owner: Owner) -> HttpResponse:
    """Bind this browser to `owner`: reuse its device row when there is one, otherwise register a new device."""
    device = get_device(request)
    if device:
        if device.owner_id != owner.id:
            device.owner = owner
            device.save(update_fields=["owner"])
        return response
    device = Device.objects.create(owner=owner, user_agent=request.META.get("HTTP_USER_AGENT", "")[:200])
    request._dv_device = device  # type: ignore[attr-defined]
    response.set_cookie(
        settings.OWNER_COOKIE,
        signing.dumps(str(device.id), salt=SALT_DEVICE),
        max_age=settings.OWNER_COOKIE_AGE,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
    )
    return response


def forget_device(request: HttpRequest, response: HttpResponse) -> HttpResponse:
    if device := get_device(request):
        device.delete()
    response.delete_cookie(settings.OWNER_COOKIE)
    return response


def email_hash(email: str) -> str:
    """Keyed hash for lookup; keyed with the encryption key so rotating SECRET_KEY doesn't orphan accounts."""
    key = (settings.FIELD_ENCRYPTION_KEY or settings.SECRET_KEY).encode()
    return hmac.new(key, email.strip().lower().encode(), hashlib.sha256).hexdigest()


LOGIN_CODE_TTL, LOGIN_MAX_TRIES, LOGIN_RESEND_AFTER = 15 * 60, 5, 45


def issue_login_code(email: str) -> str | None:
    """A 6-digit code for this email, or None while the previous one is too fresh to resend."""
    h = email_hash(email)
    if not cache.add(f"login-sent:{h}", 1, LOGIN_RESEND_AFTER):
        return None
    code = f"{secrets.randbelow(10**6):06d}"
    digest = hashlib.sha256(code.encode()).hexdigest()
    cache.set(f"login:{h}", {"email": email.strip(), "digest": digest, "tries": 0}, LOGIN_CODE_TTL)
    return code


def check_login_code(h: str, code: str) -> str | None:
    """The email the code was sent to, or None. Five wrong tries burn the code."""
    entry = cache.get(f"login:{h}")
    if not entry or entry["tries"] >= LOGIN_MAX_TRIES:
        return None
    if hmac.compare_digest(entry["digest"], hashlib.sha256(code.strip().encode()).hexdigest()):
        cache.delete(f"login:{h}")
        return entry["email"]
    cache.set(f"login:{h}", {**entry, "tries": entry["tries"] + 1}, LOGIN_CODE_TTL)
    return None


def login_link_token(email: str, code: str) -> str:
    return signing.dumps({"h": email_hash(email), "c": code}, salt=SALT_LOGIN)


def from_login_link(token: str) -> tuple[str, str] | None:
    try:
        data = signing.loads(token, salt=SALT_LOGIN, max_age=LOGIN_CODE_TTL)
    except signing.BadSignature:
        return None
    return data["h"], data["c"]


@transaction.atomic
def sign_in(
    current: Owner | None, email: str | None = None, provider: str | None = None, subject: str | None = None, trust_email: bool = True
) -> Owner:
    """The account behind an email code or a provider identity. What this device made anonymously moves into it.

    A provider's email links to an existing email account only when the provider vouches for it (`trust_email`).
    """
    account = None
    if provider and subject:
        ident = Identity.objects.select_related("owner").filter(provider=provider, subject_hash=email_hash(f"{provider}:{subject}")).first()
        account = ident.owner if ident else None
    if account is None and email and (trust_email or not provider):
        account = Owner.objects.select_for_update().filter(email_hash=email_hash(email)).first()
    if account is None:
        account = current if current and not current.is_account else Owner.objects.create()
    if email and not account.email_hash and not Owner.objects.filter(email_hash=email_hash(email)).exists():
        account.email, account.email_hash, account.email_verified_at = email.strip(), email_hash(email), timezone.now()
        account.save(update_fields=["email", "email_hash", "email_verified_at"])
    if provider and subject:
        Identity.objects.get_or_create(provider=provider, subject_hash=email_hash(f"{provider}:{subject}"), defaults={"owner": account})
    if current and current.id != account.id and not current.is_account:
        Person.objects.filter(owner=current).update(owner=account)
        Pair.objects.filter(owner=current).update(owner=account)
        Pair.objects.filter(partner=current).exclude(owner=account).update(partner=account)
        Device.objects.filter(owner=current).update(owner=account)
        current.delete()
    Pair.objects.filter(owner=account, partner=account).update(partner=None)  # merged into a pair they had joined
    return account


# ── access: the creator or the joined partner ─────────────────────────────
def pairs_of(owner: Owner) -> models.QuerySet[Pair]:
    return Pair.objects.filter(models.Q(owner=owner) | models.Q(partner=owner))


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I — easy to read aloud


def side_of(owner: Owner, pair: Pair) -> str:
    """«a» for the creator, «b» for the joined partner."""
    return "a" if pair.owner_id == owner.id else "b"


def daily_state(pair: Pair, side: str, day) -> dict:
    """Today's answers as this side may see them: the partner's text stays hidden until both have answered."""
    from .models import DailyAnswer

    rows = {r.side: r for r in DailyAnswer.objects.filter(pair=pair, day=day)}
    mine, theirs = rows.get(side), rows.get("b" if side == "a" else "a")
    both = bool(mine and theirs)
    past = DailyAnswer.objects.filter(pair=pair, day__lt=day).order_by("-day")
    by_day: dict = {}
    for r in past[:60]:
        by_day.setdefault(r.day, {})[r.side] = r
    history = [
        {"day": d, "question": rs[side].question, "mine": rs[side].text, "theirs": rs["b" if side == "a" else "a"].text}
        for d, rs in by_day.items()
        if len(rs) == 2
    ]
    return {
        "mine": mine.text if mine else "",
        "theirs": theirs.text if both and theirs else "",
        "partner_answered": bool(theirs),
        "has_partner": bool(pair.partner_id),
        "history": history,
    }


def invite_code(pair: Pair, fresh: bool = False) -> str:
    if pair.invite_code and not fresh:
        return pair.invite_code
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not Pair.objects.filter(invite_code=code).exists():
            break
    pair.invite_code = code
    pair.save(update_fields=["invite_code"])
    return code


def pair_by_code(raw: str) -> Pair | None:
    code = "".join(ch for ch in raw.upper() if ch.isalnum())
    return Pair.objects.select_related("owner", "a", "b").filter(invite_code=code).first() if len(code) == 6 else None


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


def update_person(p: Person, data: dict) -> None:
    p.name = data["name"] or p.name
    p.birth = birth_payload(data["date"], data.get("time"), data.get("place"))
    p.save(update_fields=["name", "birth"])


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
