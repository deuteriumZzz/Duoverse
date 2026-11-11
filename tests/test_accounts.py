"""Passwordless accounts, devices and the partner joining a pair (ADR-0010)."""

import re

import pytest
from django.core import mail
from django.test import Client

from apps.compatibility.models import Device, Owner, Pair
from tests.test_flows import make_pair, sign_in

pytestmark = pytest.mark.django_db(transaction=True)


def test_wrong_codes_burn_the_code_and_next_cannot_leave_the_site():
    client = Client()
    client.post("/login/", {"email": "a@example.com"})
    code = re.search(r"Ваш код: (\d{6})", mail.outbox[-1].body).group(1)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert client.post("/login/code/", {"code": wrong}).status_code == 422
    assert client.post("/login/code/", {"code": code}).status_code == 422  # burnt after five misses
    assert not Owner.objects.filter(email_hash__isnull=False).exists()
    assert sign_in(Client(), "b@example.com", "https://evil.example/") == "/account/"


def test_email_link_signs_in_once():
    client = Client()
    client.post("/login/", {"email": "a@example.com", "next": "/history/"})
    link = re.search(r"http://testserver(/login/link/[^\s]+)", mail.outbox[-1].body).group(1)
    assert client.get(link)["Location"] == "/history/"
    assert Client().get(link).status_code == 410


def test_anonymous_reports_move_into_the_account_on_another_device():
    first = Client()
    stored = make_pair(first, email="anya@example.com")
    anon = Client()
    anon.post("/new/", {"a_name": "Аня", "a_date": "1996-03-14", "b_name": "Олег", "b_date": "1990-01-20"})
    sign_in(anon, "anya@example.com")
    owner = Owner.objects.get(email_hash__isnull=False)
    assert Owner.objects.count() == 1 and owner.pairs.count() == 2 and owner.devices.count() == 2
    assert anon.get(f"/r/{stored.id}/").status_code == 200


def test_partner_sees_only_the_shared_pair_and_loses_it_when_unlinked():
    anya = Client()
    shared = make_pair(anya, email="anya@example.com")
    other = make_pair(anya, email="anya@example.com")  # another pair of Anya's — never visible to Misha
    page = anya.get(f"/r/{shared.id}/invite/").content.decode()
    code = re.search(r"/join/([A-Z0-9]{6})/", page).group(1)

    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept", "consent": "on"})
    assert misha.get(f"/r/{shared.id}/").status_code == 200
    assert misha.get(f"/r/{other.id}/").status_code == 404
    assert misha.get(f"/r/{shared.id}/invite/").status_code == 404  # only the creator invites
    assert Client().get(f"/join/{code}/").status_code == 410  # a third account can't take the pair

    misha.post(f"/p/{shared.pair.id}/unlink/")
    assert misha.get(f"/r/{shared.id}/").status_code == 404
    assert Pair.objects.get(id=shared.pair.id).invite_code != code  # old code no longer works


def test_signing_out_another_device():
    phone, laptop = Client(), Client()
    stored = make_pair(phone, email="anya@example.com")
    sign_in(laptop, "anya@example.com")
    laptop_device = Device.objects.order_by("-created_at").first()
    phone.post(f"/account/devices/{laptop_device.id}/")
    assert laptop.get(f"/r/{stored.id}/").status_code == 404
    assert phone.get(f"/r/{stored.id}/").status_code == 200


def test_inviting_needs_an_account():
    client = Client()
    client.post("/new/", {"a_date": "1996-03-14", "b_date": "1994-09-02"})  # did not sign in
    pair = Pair.objects.get()
    assert client.get(f"/p/{pair.id}/invite/")["Location"].startswith("/login/?next=")


def _provider_settings(settings):
    settings.YANDEX_CLIENT_ID, settings.YANDEX_CLIENT_SECRET = "ya-id", "ya-secret"
    settings.VK_CLIENT_ID = "vk-id"
    settings.TELEGRAM_BOT_NAME, settings.TELEGRAM_BOT_TOKEN = "duoverse_bot", "123:abc"


def test_yandex_sign_in_links_to_the_email_account(settings, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from apps.compatibility.infrastructure import oauth

    _provider_settings(settings)
    first = Client()
    stored = make_pair(first, email="anya@yandex.ru")
    calls = []

    def fake(url, data=None, headers=None):
        calls.append((url, data))
        return {"access_token": "t"} if "token" in url else {"id": "42", "default_email": "anya@yandex.ru"}

    monkeypatch.setattr(oauth, "_request", fake)
    phone = Client()
    start = phone.get("/login/yandex/?next=/history/")["Location"]
    q = parse_qs(urlparse(start).query)
    assert start.startswith("https://oauth.yandex.ru/authorize?") and q["code_challenge_method"] == ["S256"]
    assert phone.get("/login/yandex/callback/", {"code": "c", "state": "forged"}).status_code == 400
    phone.get("/login/yandex/?next=/history/")
    state = parse_qs(urlparse(phone.get("/login/yandex/")["Location"]).query)["state"][0]
    assert phone.get("/login/yandex/callback/", {"code": "c", "state": state})["Location"] == "/account/"
    assert calls[0][1]["code_verifier"] and phone.get(f"/r/{stored.id}/").status_code == 200  # same account as the email one


def test_vk_exchange_sends_device_id_and_state(settings, monkeypatch):
    from apps.compatibility.infrastructure import oauth

    _provider_settings(settings)
    sent = {}

    def fake(url, data=None, headers=None):
        sent[url] = data
        return {"access_token": "t", "user_id": 7} if url.endswith("/auth") else {"user": {"user_id": "7", "email": "m@vk.com"}}

    monkeypatch.setattr(oauth, "_request", fake)
    user = oauth.exchange("vk", {"code": "c", "device_id": "dev"}, "https://x/cb/", "verifier", "s" * 32)
    assert user.subject == "7" and not user.email_verified
    assert sent["https://id.vk.ru/oauth2/auth"]["device_id"] == "dev" and sent["https://id.vk.ru/oauth2/auth"]["state"] == "s" * 32


def test_telegram_widget_signature_is_checked(settings):
    import hashlib
    import hmac
    import time

    _provider_settings(settings)
    fields = {"id": "99", "first_name": "Миша", "auth_date": str(int(time.time()))}
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    good = hmac.new(hashlib.sha256(b"123:abc").digest(), check.encode(), hashlib.sha256).hexdigest()
    client = Client()
    assert client.get("/login/telegram/", {**fields, "hash": "0" * 64}).status_code == 400
    assert client.get("/login/telegram/", {**fields, "hash": good, "next": "/history/"})["Location"] == "/history/"
    assert Owner.objects.get().identities.filter(provider="telegram").exists()


def test_partner_edits_own_birth_data_but_cannot_delete_it():
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    code = re.search(r"/join/([A-Z0-9]{6})/", anya.get(f"/r/{stored.id}/invite/").content.decode()).group(1)
    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept", "consent": "on"})
    b = stored.pair.b
    assert misha.get(f"/profiles/{b.id}/").status_code == 200
    misha.post(f"/profiles/{b.id}/", {"name": "Миша", "date": "1994-09-03", "time": "", "place": ""})
    b.refresh_from_db()
    assert b.birth["date"] == "1994-09-03"
    misha.post(f"/profiles/{b.id}/", {"action": "delete"})
    assert type(b).objects.filter(id=b.id).exists()  # a partner can't delete the creator's records
    assert misha.get(f"/profiles/{stored.pair.a.id}/").status_code == 404  # nor touch the other side


def test_stale_anonymous_data_is_cleaned_up():
    from datetime import timedelta

    from django.core.management import call_command
    from django.utils import timezone

    Client().post("/new/", {"a_date": "1996-03-14", "b_date": "1994-09-02"})  # never signed in
    make_pair(Client(), email="kept@example.com")
    Owner.objects.update(created_at=timezone.now() - timedelta(days=8))
    call_command("scheduled_jobs")
    assert Owner.objects.count() == 1 and Owner.objects.get().is_account


def _linked_pair():
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    code = re.search(r"/join/([A-Z0-9]{6})/", anya.get(f"/r/{stored.id}/invite/").content.decode()).group(1)
    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept", "consent": "on"})
    return anya, misha, stored


def test_question_of_day_opens_only_when_both_answered():
    from datetime import timedelta

    from django.utils import timezone

    from apps.compatibility.models import DailyAnswer

    anya, misha, stored = _linked_pair()
    anya.post("/daily/answer/", {"text": "Вечер у реки"})
    misha_page = misha.get("/daily/").content.decode()
    assert "Вечер у реки" not in misha_page and "уже ответил" in misha_page  # hidden, but Misha knows Anya answered
    assert "Откроется, когда" in anya.get("/daily/").content.decode()
    misha.post("/daily/answer/", {"text": "Поездка в горы"})
    page = anya.get("/daily/").content.decode()
    assert "Вечер у реки" in page and "Поездка в горы" in page
    rows = DailyAnswer.objects.filter(pair=stored.pair)
    assert {r.side for r in rows} == {"a", "b"} and len({r.question for r in rows}) == 1  # same server-side question
    rows.update(day=timezone.localdate() - timedelta(days=1))
    assert "История ваших ответов (1)" in anya.get("/daily/").content.decode()  # free: a teaser
    from apps.compatibility.access import mark_paid
    from apps.compatibility.models import Purchase

    mark_paid(Purchase.objects.create(owner=stored.pair.partner, kind="plus", amount=249))  # Misha's «Пара+» covers Anya too
    assert "Ваши прошлые ответы" in anya.get("/daily/").content.decode()


def test_answer_without_partner_invites_them():
    anya = Client()
    make_pair(anya, email="anya@example.com")
    anya.post("/daily/answer/", {"text": "Утро без будильника"})
    assert "ещё не в паре" in anya.get("/daily/").content.decode()


def test_partner_hears_about_answers_by_telegram_or_email(settings, monkeypatch):
    from apps.compatibility.infrastructure import telegram

    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda chat, text, url="": sent.append((chat, text)) or True)
    anya, misha, stored = _linked_pair()
    mail.outbox.clear()
    anya.post("/daily/answer/", {"text": "Вечер у реки"})
    assert "Аня ответил(а) на вопрос дня" in mail.outbox[-1].body and mail.outbox[-1].to == ["misha@example.com"]  # no Telegram yet

    settings.TELEGRAM_BOT_NAME, settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_WEBHOOK_SECRET = "duoverse_bot", "1:x", "s3cret"
    start = anya.get("/account/telegram/")["Location"]
    code = start.split("start=")[1]
    hook = "/telegram/s3cret/"
    assert Client().post(hook, {}, content_type="application/json").status_code == 404  # no secret header
    Client().post(
        hook,
        {"message": {"chat": {"id": 777}, "text": f"/start {code}"}},
        content_type="application/json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="s3cret",
    )
    assert stored.pair.owner.__class__.objects.get(id=stored.pair.owner_id).telegram_chat_id == 777
    misha.post("/daily/answer/", {"text": "Поездка в горы"})
    assert sent[-1][0] == 777 and "Миша ответил(а)" in sent[-1][1]


def test_evening_reminder_once_for_linked_owner_without_answer(settings, monkeypatch):
    from datetime import datetime

    from django.core.management import call_command
    from django.utils import timezone

    from apps.compatibility.infrastructure import telegram

    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda chat, text, url="": sent.append(text) or True)
    anya, misha, stored = _linked_pair()
    Owner.objects.filter(id=stored.pair.owner_id).update(telegram_chat_id=1)
    evening = timezone.make_aware(datetime.combine(timezone.localdate(), datetime.min.time()).replace(hour=settings.REMINDER_HOUR))
    monkeypatch.setattr(timezone, "localtime", lambda *a: evening)
    call_command("scheduled_jobs")
    call_command("scheduled_jobs")
    assert len([t for t in sent if "Вопрос дня ждёт" in t]) == 1


def test_app_can_be_installed():
    manifest = Client().get("/manifest.webmanifest").json()
    assert manifest["display"] == "standalone" and any(i["purpose"] == "maskable" for i in manifest["icons"])
    assert b"offline" in Client().get("/sw.js").content


def test_cabinet_avatar_invite_and_shared_tracker_with_marks_per_person():
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    pair = stored.pair
    cabinet = anya.get("/account/").content.decode()
    assert "Моя пара" in cabinet and "Пригласите Мишу" in cabinet and "/join/" in cabinet  # invite sheet with link and QR
    assert "Пригласить Мишу" in anya.get(f"/r/{stored.id}/").content.decode()  # the «+» next to her avatar

    anya.post("/account/profile/", {"name": "Аня", "avatar": "anchor"})
    anya.post("/account/profile/", {"avatar": "<script>"})  # unknown keys are ignored
    owner = Owner.objects.get(id=pair.owner_id)
    assert (owner.name, owner.avatar) == ("Аня", "anchor")
    assert 'aria-label="Якорь"' in anya.get("/account/").content.decode()  # header menu and profile

    code = re.search(r"/join/([A-Z0-9]{6})/", cabinet).group(1)
    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept", "consent": "on"})
    title = anya.get(f"/r/{stored.id}/habits/").context["r"].habits[0].title
    anya.post("/plan/pick/", {"rid": stored.id, "habit": [title]})
    mine = anya.post("/plan/done/", {"rid": stored.id, "habit": title}).json()["habits"][0]
    assert mine["today"] and not mine["partner"]
    theirs = misha.post("/plan/done/", {"rid": stored.id, "habit": title}).json()["habits"][0]
    assert theirs["today"] and theirs["partner"]  # Misha sees his own mark and Anya's
    assert "Пригласить" not in anya.get(f"/r/{stored.id}/").content.decode().split("<nav")[0]  # joined: no «+» anymore


def test_visitors_without_an_account_get_a_sign_in_button():
    page = Client().get("/").content.decode()
    assert 'aria-label="Профиль"' not in page and "Войти" in page
