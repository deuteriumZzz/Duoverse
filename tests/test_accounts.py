"""Passwordless accounts, devices and the partner joining a pair (ADR-0010)."""

import re

import pytest
from django.core import mail
from django.test import Client
from django.utils import timezone

from apps.compatibility.models import Device, Owner, Pair, Purchase
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

    import json

    from apps.compatibility.infrastructure.demo import answers_for
    from apps.compatibility.models import DailyAnswer

    misha.post(f"/join/{code}/", {"answers": json.dumps(answers_for("misha"))})  # Misha's own questionnaire
    misha.post("/daily/answer/", {"text": "Вечер у реки"})
    assert Pair.objects.get(id=shared.pair.id).b.answers

    misha.post(f"/p/{shared.pair.id}/unlink/")
    assert misha.get(f"/r/{shared.id}/").status_code == 404
    pair = Pair.objects.get(id=shared.pair.id)
    assert not pair.b.answers and not DailyAnswer.objects.filter(pair=pair, side="b").exists()  # what Misha gave leaves with Misha
    assert pair.reports.count() == 1 and not pair.reports.get().snapshot["psychology"]["available"]  # recounted without it
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
    Purchase.objects.filter(kind="trial").update(valid_until=timezone.now())  # past the joining week of «Пара+»
    page = anya.get("/daily/").content.decode()  # yesterday in the week strip: the diary is «Пара+», free shows a lock
    assert "Дневник пары — в «Паре+»" in page and "Поездка в горы" not in page
    from apps.compatibility.access import mark_paid

    mark_paid(Purchase.objects.create(owner=stored.pair.partner, kind="plus", amount=249))  # Misha's «Пара+» covers Anya too
    page = anya.get("/daily/").content.decode()
    assert "Вечер у реки" in page and "Поездка в горы" in page  # yesterday's question and both answers


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


def test_both_partners_hear_the_evening_before_the_free_week_of_plus_ends(settings, monkeypatch):
    from datetime import datetime, timedelta

    from django.core.management import call_command

    from apps.compatibility.infrastructure import telegram

    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda chat, text, url="": sent.append((chat, text)) or True)
    anya, misha, stored = _linked_pair()
    pair = Pair.objects.get(id=stored.pair_id)
    Owner.objects.filter(id=pair.owner_id).update(telegram_chat_id=1)
    Owner.objects.filter(id=pair.partner_id).update(telegram_chat_id=2)
    trial = Purchase.objects.get(kind="trial")
    Purchase.objects.filter(id=trial.id).update(valid_until=timezone.now() + timedelta(hours=10))
    evening = timezone.make_aware(datetime.combine(timezone.localdate(), datetime.min.time()).replace(hour=settings.REMINDER_HOUR))
    monkeypatch.setattr(timezone, "localtime", lambda *a: evening)
    paid = Purchase.objects.create(owner_id=pair.partner_id, kind="plus", amount=249, status="succeeded",
                                   valid_until=timezone.now() + timedelta(days=30))  # fmt: skip
    call_command("scheduled_jobs")
    assert not [t for _, t in sent if "Подарочная неделя" in t]  # Misha already pays: nothing closes, nothing to say
    paid.delete()
    call_command("scheduled_jobs")
    call_command("scheduled_jobs")
    told = sorted(chat for chat, t in sent if "Подарочная неделя" in t)
    assert told == [1, 2]  # both partners, once each


def test_invite_nudge_once_when_the_partner_has_not_joined(settings, monkeypatch):
    from datetime import datetime, timedelta

    from django.core.management import call_command

    from apps.compatibility.infrastructure import telegram

    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda chat, text, url="": sent.append(text) or True)
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    anya.get(f"/r/{stored.id}/invite/")  # the invite exists, nobody joined
    Pair.objects.filter(id=stored.pair_id).update(created_at=timezone.now() - timedelta(days=3))
    Owner.objects.filter(id=stored.pair.owner_id).update(telegram_chat_id=1)
    evening = timezone.make_aware(datetime.combine(timezone.localdate(), datetime.min.time()).replace(hour=settings.REMINDER_HOUR))
    monkeypatch.setattr(timezone, "localtime", lambda *a: evening)
    call_command("scheduled_jobs")
    call_command("scheduled_jobs")
    assert len([t for t in sent if "Приглашение в пару ждёт" in t and "Миша" in t]) == 1  # once, not every evening


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
    title = anya.get("/daily/").context["r"].habits[0].title  # habits are picked in «Сегодня»
    anya.post("/plan/pick/", {"rid": stored.id, "habit": [title]})
    mine = anya.post("/plan/done/", {"rid": stored.id, "habit": title}).json()["habits"][0]
    assert mine["today"] and not mine["partner"]
    theirs = misha.post("/plan/done/", {"rid": stored.id, "habit": title}).json()["habits"][0]
    assert theirs["today"] and theirs["partner"]  # Misha sees his own mark and Anya's
    assert "Пригласить" not in anya.get(f"/r/{stored.id}/").content.decode().split("<nav")[0]  # joined: no «+» anymore


def test_visitors_without_an_account_get_a_sign_in_button():
    page = Client().get("/").content.decode()
    assert 'aria-label="Профиль"' not in page and "Войти" in page


def test_pair_week_is_built_from_the_report_and_marked_by_both():
    from apps.compatibility.access import mark_paid

    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    page = anya.get("/daily/").content.decode()
    assert "Неделя пары" in page and "Начать неделю пары" in page
    anya.post("/week/start/", {"rid": stored.id})
    pair = Pair.objects.get(id=stored.pair_id)
    week = pair.plan["week"]
    assert len(week["days"]) == 7 and week["days"][0]["kind"] == "talk" and week["days"][-1]["kind"] == "reflect"
    weakest = min(stored.snapshot["spheres"], key=lambda s: s["score"])["key"]
    assert week["days"][0]["sphere"] == weakest  # the week starts where the pair is most sensitive

    s = anya.post("/week/done/", {"rid": stored.id, "day": 1}).json()
    assert s["days"][0]["mine"] and not s["days"][0]["both"]
    assert anya.post("/week/done/", {"rid": stored.id, "day": 2}).status_code == 403  # locked and not today yet

    code = re.search(r"/join/([A-Z0-9]{6})/", anya.get("/account/").content.decode()).group(1)
    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept", "consent": "on"})
    both = misha.post("/week/done/", {"rid": stored.id, "day": 1}).json()
    assert both["days"][0]["both"] and both["done"] == 1

    mark_paid(Purchase.objects.create(owner_id=pair.owner_id, pair=pair, kind="deep", amount=490))
    assert not anya.post("/week/done/", {"rid": stored.id, "day": 1}).json()["days"][1]["locked"]  # unlocked after the purchase


def test_full_report_preview_names_what_this_pair_gets():
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    razbor = anya.get(f"/r/{stored.id}/razbor/").content.decode()
    assert "Что откроется для" in razbor and "сфер целиком" in razbor and "Неделя пары: 7 шагов" in razbor


def test_pair_story_shows_the_timeline_and_asks_for_a_new_look_after_three_months():
    from datetime import timedelta

    from apps.compatibility.models import StoredReport

    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    page = anya.get(f"/p/{stored.pair_id}/story/").content.decode()
    assert "Первый разбор пары" in page and "Посмотрите на пару заново" not in page
    assert Client().get(f"/p/{stored.pair_id}/story/").status_code == 404  # only the pair itself

    StoredReport.objects.filter(id=stored.id).update(created_at=timezone.now() - timedelta(days=95))
    assert "Посмотрите на пару заново" in anya.get(f"/p/{stored.pair_id}/story/").content.decode()  # three months on
    snap = {**stored.snapshot, "total_score": stored.snapshot["total_score"] + 4}  # a new look after the questionnaires again
    StoredReport.objects.create(pair=stored.pair, status=StoredReport.Status.READY, snapshot=snap)
    page = anya.get(f"/p/{stored.pair_id}/story/").content.decode()
    assert "Новый разбор" in page and "Посмотрите на пару заново" not in page


def test_weekly_talk_counts_when_both_marked():
    anya, misha, stored = _linked_pair()
    page = anya.get("/daily/").content.decode()
    assert "«Как мы?»" in page  # «Погода пары» depends on the week's sky; apps/astrology/domain/weather.py checks itself
    anya.post("/talk/done/")
    assert "поговорили на этой неделе" not in anya.get("/daily/").content.decode()  # one mark is not a talk
    misha.post("/talk/done/")
    assert "поговорили на этой неделе" in anya.get("/daily/").content.decode()


def test_intimacy_shows_only_what_both_chose_and_leaves_with_the_partner():
    from apps.compatibility.models import IntimacyAnswer

    anya, misha, stored = _linked_pair()
    assert "Близость" in anya.get("/pair/").content.decode()  # «Вдвоём» holds what is «ours»
    anya.post("/intimacy/", {"hug": "yes", "role": "maybe", "trip": "yes", "place": "no"})
    page = misha.get("/intimacy/").content.decode()
    assert "ответы уже есть" in page and "Вы оба хотите" not in page  # nothing of Anya's shows before Misha answers
    misha.post("/intimacy/", {"hug": "yes", "role": "yes", "trip": "no", "place": "yes"})
    page = anya.get("/intimacy/").content.decode()
    both = page.split("Вы оба хотите")[1].split("</section>")[0]
    assert "Долгие объятия" in both and "Ролевая игра" in both  # «да»+«да», then «да»+«может быть» to talk about
    assert "Спонтанная поездка" not in both and "непривычном месте" not in both  # a «нет» never shows
    assert IntimacyAnswer.objects.get(side="a").picks["hug"] == "yes"
    misha.post(f"/p/{stored.pair_id}/unlink/")
    assert not IntimacyAnswer.objects.filter(side="b").exists()  # leaves with the partner


def test_pair_calendar_is_shared_and_a_birthday_is_told_only_to_the_partner(settings, monkeypatch):
    import json
    from datetime import datetime, timedelta

    from django.core.management import call_command

    from apps.compatibility.infrastructure import telegram
    from apps.compatibility.models import Person

    anya, misha, stored = _linked_pair()
    today = timezone.localdate()
    assert anya.post("/calendar/", {"kind": "met", "day": (today - timedelta(days=993)).isoformat()}).status_code == 302
    misha.post("/calendar/", {"title": "Поездка в Казань", "day": (today + timedelta(days=30)).isoformat(), "note": "билеты в почте"})
    assert misha.post("/calendar/", {"title": "Слишком далеко", "day": (today + timedelta(days=400)).isoformat()}).status_code == 422
    page = anya.get("/calendar/").content.decode()
    assert "993" in page and "Поездка в Казань" in page and "билеты в почте" in page and "День рождения Миши" in page
    assert "весь календарь" in anya.get("/daily/").content.decode() and "Календарь" in anya.get("/pair/").content.decode()

    pair = Pair.objects.get(id=stored.pair_id)
    misha_person = Person.objects.get(id=pair.b_id)
    born = today + timedelta(days=7)
    misha_person.birth = {**misha_person.birth, "date": born.replace(year=born.year - 28).isoformat()}
    misha_person.save()
    Owner.objects.filter(id=pair.owner_id).update(telegram_chat_id=1)
    Owner.objects.filter(id=pair.partner_id).update(telegram_chat_id=2)
    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda chat, text, url="": sent.append((chat, text)) or True)
    evening = timezone.make_aware(datetime.combine(today, datetime.min.time()).replace(hour=settings.REMINDER_HOUR))
    monkeypatch.setattr(timezone, "localtime", lambda *a: evening)
    call_command("scheduled_jobs")
    call_command("scheduled_jobs")
    assert [c for c, t in sent if "день рождения у Миши" in t] == [1]  # only Anya hears, and only once
    assert sorted(c for c, t in sent if "1000 дней со знакомства" in t) == [1, 2]  # the milestone is for both

    assert json.loads(anya.get("/account/export/").content)["dates"][0]["entries"]
    misha.post(f"/p/{stored.pair_id}/unlink/")
    left = Pair.objects.get(id=stored.pair_id).dates
    assert [e["kind"] for e in left] == ["met"]  # Misha's trip left with him, Anya's day stays


def test_wish_map_reservation_stays_hidden_from_the_owner_and_feeds_the_birthday_reminder(settings, monkeypatch):
    import json
    from datetime import datetime, timedelta

    from django.core.management import call_command

    from apps.compatibility.access import mark_paid
    from apps.compatibility.infrastructure import telegram
    from apps.compatibility.models import Person

    anya, misha, stored = _linked_pair()
    anya.post("/wishes/", {"kind": "experience", "title": "Мастер-класс по керамике", "link": "https://example.com/clay"})
    assert anya.post("/wishes/", {"title": "x", "link": "javascript:alert(1)"}).status_code == 422
    misha.post("/wishes/", {"kind": "dream", "title": "Поехать в Японию"})
    wish_id = Pair.objects.get(id=stored.pair_id).wishes[0]["id"]
    Purchase.objects.filter(kind="trial").update(valid_until=timezone.now())  # the joining week of «Пара+» is over
    misha.post("/wishes/", {"action": "reserve", "id": wish_id})
    assert not Pair.objects.get(id=stored.pair_id).wishes[0]["taken"]  # the quiet reservation is «Пара+»
    mark_paid(Purchase.objects.create(owner=stored.pair.partner, kind="plus", amount=249))
    misha.post("/wishes/", {"action": "reserve", "id": wish_id})
    assert "Забронировано вами" in misha.get("/wishes/").content.decode()
    page = anya.get("/wishes/").content.decode()
    assert "Мастер-класс по керамике" in page and "Поехать в Японию" in page and "Забронировано" not in page
    assert json.loads(anya.get("/account/export/").content)["wishes"][0]["mine"][0]["taken"] == ""  # not even in her export

    pair = Pair.objects.get(id=stored.pair_id)
    anya_person = Person.objects.get(id=pair.a_id)
    born = timezone.localdate() + timedelta(days=7)
    anya_person.birth = {**anya_person.birth, "date": born.replace(year=born.year - 28).isoformat()}
    anya_person.save()
    Owner.objects.filter(id=pair.partner_id).update(telegram_chat_id=2)
    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda chat, text, url="": sent.append(text) or True)
    evening = timezone.make_aware(datetime.combine(timezone.localdate(), datetime.min.time()).replace(hour=settings.REMINDER_HOUR))
    monkeypatch.setattr(timezone, "localtime", lambda *a: evening)
    call_command("scheduled_jobs")
    assert any("день рождения у Ани" in t and "В карте желаний 1 идея, одну вы уже забронировали" in t for t in sent)

    misha.post(f"/p/{stored.pair_id}/unlink/")
    left = Pair.objects.get(id=stored.pair_id).wishes
    assert [w["title"] for w in left] == ["Мастер-класс по керамике"] and left[0]["taken"] == ""  # his dream and reservation go


def test_date_of_the_week_offers_18_plus_only_from_mutual_yes_after_both_switch_it_on(settings, monkeypatch):
    from datetime import datetime, timedelta

    from django.core.management import call_command

    from apps.compatibility import date_ideas
    from apps.compatibility.infrastructure import telegram

    anya, misha, stored = _linked_pair()
    assert "свидание недели" in anya.get("/daily/").content.decode()
    anya.post("/intimacy/", {"hug": "yes", "trip": "yes"})
    misha.post("/intimacy/", {"hug": "yes", "trip": "no"})
    anya.post("/intimacy/", {"action": "date18"})
    calls = []
    real = date_ideas.pick
    monkeypatch.setattr(date_ideas, "pick", lambda *a: calls.append(a) or real(*a))
    assert "Вы согласились" in anya.get("/intimacy/").content.decode()
    anya.get("/daily/")
    assert calls[-1][4] == ["hug"] and calls[-1][5] is False  # only the mutual «да»; off until Misha agrees too
    misha.post("/intimacy/", {"action": "date18"})
    anya.get("/daily/")
    assert calls[-1][5] is True

    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda chat, text, url="": sent.append(text) or True)
    pair = Pair.objects.get(id=stored.pair_id)
    Owner.objects.filter(id__in=[pair.owner_id, pair.partner_id]).update(telegram_chat_id=1)
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    evening = timezone.make_aware(datetime.combine(monday, datetime.min.time()).replace(hour=settings.REMINDER_HOUR))
    monkeypatch.setattr(timezone, "localtime", lambda *a: evening)
    call_command("scheduled_jobs")
    call_command("scheduled_jobs")
    ideas = [t for t in sent if "идея на эту неделю" in t]
    assert len(ideas) == 2 and not any("18" in t or "Близост" in t for t in ideas)  # both, once, in neutral words


def test_we_did_it_counts_when_both_mark_and_the_calendar_and_wish_map_celebrate():
    from datetime import timedelta

    anya, misha, stored = _linked_pair()
    assert anya.post("/idea/done/")["Location"].endswith("/daily/#date-idea")  # one mark is not a date yet
    assert "together=1" in misha.post("/idea/done/")["Location"]  # the second one is: confetti on the way back
    page = anya.get("/daily/").content.decode()
    assert "Свиданий вместе: 1" in page and "Вы отметили" in page and "засчитано вам двоим" in page

    today = timezone.localdate()
    anya.post("/calendar/", {"kind": "met", "day": (today - timedelta(days=100)).isoformat()})
    cal = anya.get("/calendar/").content.decode()
    assert "Сегодня: 100 дней со знакомства!" in cal and "До 200 дней со знакомства — ещё 100 дн." in cal
    pages = page + cal + anya.get("/quiz/").content.decode() + anya.get("/wishes/").content.decode()
    assert "{#" not in pages and "#}" not in pages  # a template comment spread over lines would print as text

    anya.post("/wishes/", {"kind": "thing", "title": "Книга про Японию"})
    misha.post("/wishes/", {"kind": "dream", "title": "Поехать в Японию"})
    gift, dream = (w["id"] for w in Pair.objects.get(id=stored.pair_id).wishes)
    assert f"?tied={gift}" in misha.post("/wishes/", {"action": "reserve", "id": gift})["Location"]  # the joining week of «Пара+»
    assert "sc-tie" in misha.get(f"/wishes/?tied={gift}").content.decode()
    assert "sc-tie" not in anya.get(f"/wishes/?tied={gift}").content.decode()  # never on the owner's side, even by URL
    assert f"?lit={dream}" in anya.post("/wishes/", {"action": "done", "id": dream})["Location"]
    assert "sc-lit" in anya.get(f"/wishes/?lit={dream}").content.decode()


def test_together_space_nudge_thanks_tree_and_what_leaves_with_the_partner(settings, monkeypatch):
    from apps.compatibility.infrastructure import telegram

    anya, misha, stored = _linked_pair()
    pair = Pair.objects.get(id=stored.pair_id)
    Owner.objects.filter(id=pair.owner_id).update(telegram_chat_id=1)
    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda chat, text, url="": sent.append(text) or True)
    page = anya.get("/pair/").content.decode()
    assert "наше дерево" in page and "Семечко" in page and "Думаю о тебе" in page  # the space, not a redirect to the report

    assert "sent=nudge" in misha.post("/pair/nudge/")["Location"]
    misha.post("/pair/nudge/")
    misha.post("/pair/nudge/")
    assert "sent=enough" in misha.post("/pair/nudge/")["Location"]  # three a day is plenty
    assert [t for t in sent if "думает о вас" in t] == ["Миша думает о вас."] * 3
    misha.post("/pair/thanks/", {"text": "вчерашний ужин"})
    assert any("спасибо" in t for t in sent) and not any("ужин" in t for t in sent)  # the words stay in the app
    page = anya.get("/pair/").content.decode()
    assert "Миша недавно" in page and "за вчерашний ужин" in page and "думает о вас" in page

    anya.post("/daily/answer/", {"text": "Вечер у реки"})
    misha.post("/daily/answer/", {"text": "Поездка в горы"})
    page = anya.get("/pair/").content.decode()
    assert "Росток" in page and "полито сегодня" in page  # both answered today: a leaf, and the tree is watered
    assert "ответ на вопрос дня" in page

    misha.post(f"/p/{stored.pair_id}/unlink/")
    assert Pair.objects.get(id=stored.pair_id).notes == []  # his «Думаю о тебе» and thank-you leave with him


def test_gender_is_optional_and_gives_the_right_endings_and_hair(settings, monkeypatch):
    from apps.compatibility.infrastructure import telegram
    from apps.compatibility.models import Person

    anya, misha, stored = _linked_pair()
    pair = Pair.objects.get(id=stored.pair_id)
    misha.post(f"/profiles/{pair.b_id}/", {"name": "Миша", "gender": "m", "date": "1994-09-02"})
    assert Person.objects.get(id=pair.b_id).gender == "m"
    Person.objects.filter(id=pair.a_id).update(gender="f")
    Owner.objects.filter(id=pair.owner_id).update(telegram_chat_id=1)
    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda chat, text, url="": sent.append(text) or True)
    misha.post("/daily/answer/", {"text": "Поездка в горы"})
    assert any(t.startswith("Миша ответил на вопрос дня") for t in sent)  # not «ответил(а)»
    page = anya.get("/daily/").content.decode()
    assert "Миша уже ответил —" in page and "ответил(а)" not in page
    together = anya.get("/pair/").content.decode()
    assert "#sc-hair-f" in together and "#sc-hair-m" in together  # her hair on the peach figure, his on the cobalt one


def test_a_couple_opens_on_together_with_their_path_and_todays_line():
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    assert anya.get("/")["Location"] == "/pair/"  # signed in, «Главная» is the pair
    home = anya.get("/pair/").content.decode()  # before the partner joins it is still home: the invite is step one on it
    assert "шаг 1 из 3" in home and "/invite/" in home and "Думаю о тебе" not in home and 'id="tree"' in home
    tabs = anya.get("/daily/").content.decode().split('aria-label="Нижнее меню"')[1]
    assert "Вдвоём" not in tabs and tabs.index("Главная") < tabs.index("Сегодня") and 'href="/pair/"' in tabs  # Главная = the pair
    assert f'href="/r/{stored.id}/"' in tabs  # «Отчёт» = their own report
    head = anya.get("/daily/").content.decode().split('aria-label="Основное меню"')[1].split("</nav>")[0]
    assert head.index("Главная") < head.index("Сегодня") and "Вдвоём" not in head  # the same on a computer
    assert "путь пары" not in anya.get("/?about").content.decode()  # the page about Duoverse is one link away
    assert Client().get("/").status_code == 200  # guests still see it first
    code = re.search(r"/join/([A-Z0-9]{6})/", anya.get(f"/r/{stored.id}/invite/").content.decode()).group(1)
    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept", "consent": "on"})
    page = anya.get("/pair/").content.decode()
    assert "шаг 2 из 3" in page and "Анкеты вдвоём" in page and "Пройти анкету" in page
    assert "Вопрос дня ждёт вас" not in page and "из 100 ·" not in page  # one next step on the home; the score is in «Отчёт»
    assert "Быстрый старт" not in page and "Быстрый старт" in Client().get("/").content.decode()  # no site footer inside the app
    misha.post("/daily/answer/", {"text": "Поездка в горы"})
    assert "уже ответил(а) — ответьте" in anya.get("/daily/").content.decode()


def test_a_guest_has_one_home_and_today_says_it_is_a_sample():
    visitor = Client()
    assert visitor.get("/pair/")["Location"] == "/#pair"  # no pair yet: home tells what a couple gets
    home = visitor.get("/").content.decode()
    assert 'id="pair"' in home and "Ваше пространство" in home and "Разбор — это" in home  # not only a report
    tabs = home.split('aria-label="Нижнее меню"')[1].split("</nav>")[0]
    assert tabs.count("<li>") == 4 and "Вдвоём" not in tabs  # Главная, Сегодня, Отчёт, Профиль — the same four as a couple's
    assert 'href="/report/"' in tabs  # no report of your own yet: «Отчёт» is the sample
    today = visitor.get("/daily/").content.decode()
    assert "Это пример из разбора" in today and "guest: true" in today  # «Сегодня» is to look at: habit taps ask to sign in
    assert "Ведите план вдвоём" in visitor.get("/login/?sheet=1&why=plan").content.decode()
    visitor.post("/new/", {"mode": "quick", "a_name": "Аня", "a_date": "1996-03-14", "b_name": "Миша", "b_date": "1994-09-02"})
    assert visitor.get("/pair/")["Location"].startswith("/login/")  # a report but no account: sign in, then invite
    tabs = visitor.get("/daily/").content.decode().split('aria-label="Нижнее меню"')[1].split("</nav>")[0]
    assert 'href="/r/' in tabs and 'href="/report/"' not in tabs  # «Отчёт» is now their own report, not the sample
    assert "/story/" not in visitor.get("/history/").content.decode()  # the pair story needs an account
    assert "Это пример." in visitor.get("/daily/").content.decode()


def test_an_english_browser_still_gets_one_language_russian():
    r = Client().get("/pricing/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
    assert r.headers["Content-Language"] == "ru"  # so dates and Django's own messages stay Russian too


def test_the_profile_can_unlink_delete_or_leave_a_pair():
    anya, misha, stored = _linked_pair()
    pid = stored.pair_id
    page, his = anya.get("/account/").content.decode(), misha.get("/account/").content.decode()
    assert "Отвязать партнёра" in page and "Удалить пару" in page
    assert "Выйти из пары" in his and "Удалить пару" not in his
    assert misha.post(f"/p/{pid}/delete/").status_code == 404  # a partner leaves; only the creator deletes
    assert misha.post(f"/p/{pid}/unlink/", {"next": "/account/#pair"})["Location"] == "/account/#pair"
    assert Pair.objects.get(id=pid).partner_id is None
    Purchase.objects.create(owner_id=stored.pair.owner_id, pair_id=pid, kind="deep", amount=490, status="succeeded")
    assert anya.post(f"/p/{pid}/delete/")["Location"] == "/account/#pair"
    assert not Pair.objects.filter(id=pid).exists() and Purchase.objects.filter(kind="deep", pair=None).exists()  # receipts stay


def test_habits_are_picked_and_kept_in_today():
    from apps.compatibility.services import report_of

    anya, misha, stored = _linked_pair()
    rid = stored.id
    assert anya.get(f"/r/{rid}/habits/")["Location"] == "/daily/#habits"  # the old report tab opens the sheet in «Сегодня»
    assert f"/r/{rid}/habits/" not in anya.get(f"/r/{rid}/").content.decode()  # the report explains, «Сегодня» is for doing
    title = report_of(stored).habits[0].title
    page = anya.get("/daily/").content.decode()
    assert title in page and "В план" in page and "Привычки из вашего разбора" in page  # nothing picked yet: the choice is here
    assert anya.post("/plan/pick/", {"rid": rid, "habit": [title]}).json()["picked"] == [title]
    assert "Ваш план на неделю" in anya.get("/daily/").content.decode()


def test_more_habits_to_pick_and_a_new_week_after_seven_days():
    from datetime import timedelta

    anya, misha, stored = _linked_pair()
    rid, pid = stored.id, stored.pair_id
    from apps.compatibility.services import report_of
    from apps.web.views import _habit_pool, _habits_now

    report, today = report_of(stored), timezone.localdate()
    pool = _habit_pool(report)
    assert len(pool) == 24 and len({h.title for h in pool}) == 24  # eight per weakest sphere, no repeats
    now = anya.get("/daily/").context["habits_now"]
    assert [h.title for h, _ in now] == [h.title for h in report.habits] and not any(new for _, new in now)  # week one: the report's six
    later = _habits_now(report, today - timedelta(days=7), today, [])
    assert len(later) == 6 and sum(new for _, new in later) == 2  # every Monday two new ones come in, marked «новая»
    extra = pool[-1].title
    assert anya.post("/plan/pick/", {"rid": rid, "habit": [extra]}).json()["picked"] == [extra]  # any of the pool counts
    assert extra in [h.title for h, _ in anya.get("/daily/").context["habits_now"]]  # and a picked one stays on the list

    anya.post("/week/start/", {"rid": rid})
    pair = Pair.objects.get(id=pid)
    first = [d["title"] for d in pair.plan["week"]["days"]]
    pair.plan = {**pair.plan, "week": {**pair.plan["week"], "started": (timezone.localdate() - timedelta(days=8)).isoformat()}}
    pair.save(update_fields=["plan"])
    assert "Неделя позади" in anya.get("/daily/").content.decode()
    anya.post("/week/start/", {"rid": rid})
    week = Pair.objects.get(id=pid).plan["week"]
    assert week["round"] == 1 and week["started"] == timezone.localdate().isoformat()
    assert [d["title"] for d in week["days"]] != first  # new talks and exercises, not the same seven again


def test_the_path_opens_step_by_step_and_follows_quiz_answers():
    from datetime import timedelta

    from apps.compatibility.models import QuizAnswer
    from apps.web.views import _quiz_of_week

    anya, misha, stored = _linked_pair()
    pair = Pair.objects.get(id=stored.pair_id)
    today = timezone.localdate()
    quiz = _quiz_of_week(pair, today)
    assert quiz["level"] == 1  # a new pair starts with a light quiz, not jealousy or intimacy
    daily = anya.get("/daily/").content.decode()
    assert "Скоро откроются" in daily and "Квиз недели · через" in daily  # not everything on day one
    home = anya.get("/pair/").content.decode()
    assert "этап пары · 1 из 3" in home and "Знакомство заново" in home

    Pair.objects.filter(id=pair.id).update(created_at=timezone.now() - timedelta(days=12))  # two weeks in: talk and quiz open
    for side, picks in (("a", [0, 0, 0, 0, 0, 0]), ("b", [1, 1, 0, 0, 0, 0])):
        QuizAnswer.objects.create(pair=pair, side=side, quiz_key=quiz["key"], picks=picks)
    daily = anya.get("/daily/").content.decode()
    assert "Скоро откроются" not in daily and f"в квизе «{quiz['title']}» вы ответили по-разному в 2 из 6" in daily
    QuizAnswer.objects.filter(pair=pair).update(created_at=timezone.now() - timedelta(days=8))  # done before this Monday
    assert _quiz_of_week(pair, today)["key"] != quiz["key"]  # next week brings the next one


def test_the_library_shows_what_is_open_and_the_path_what_is_ahead():
    from apps.knowledge.infrastructure.repository import KnowledgeRepository
    from apps.web.views import _quiz_of_week

    assert Client().get("/library/")["Location"] == "/#pair"  # a guest: the landing says what a couple gets
    anya, misha, stored = _linked_pair()
    pair = Pair.objects.get(id=stored.pair_id)
    page = anya.get("/library/").content.decode()
    assert "квиз этой недели" in page and "На этапе «Глубже» — ещё 22 квиза" in page and "На этапе «Откровенно» — ещё 10 квизов" in page
    assert "Открыты сейчас" in page and page.count('class="w-40 shrink-0 snap-start"') == 19  # the rest of the light ones, in a row
    assert "Все темы" in page and "Быт и деньги" in page  # topics filter what is open and done, like couple apps do
    week = _quiz_of_week(pair, timezone.localdate())
    light = next(q for q in KnowledgeRepository().series("QUIZ:") if q.get("level") == 1 and q["key"] != week["key"])
    deep = next(q for q in KnowledgeRepository().series("QUIZ:") if q.get("level") == 3)
    assert light["title"] in anya.get(f"/daily/quiz/?q={light['key']}").content.decode()  # any open quiz, from the library
    assert deep["title"] not in anya.get(f"/daily/quiz/?q={deep['key']}").content.decode()  # never one the path hasn't reached
    home = anya.get("/pair/").content.decode()
    assert "Что вас ждёт" in home and "Самые личные разговоры" in home and "вы здесь" in home  # the whole path, ahead of time


def test_the_tree_keeps_changing_after_it_is_big_and_the_story_remembers():
    from datetime import timedelta

    from apps.compatibility.models import DailyAnswer

    anya, misha, stored = _linked_pair()
    pair = Pair.objects.get(id=stored.pair_id)
    today = timezone.localdate()
    days = [DailyAnswer(pair=pair, side=s, day=today - timedelta(days=n), question="q", text="ok") for n in range(1, 101) for s in "ab"]
    DailyAnswer.objects.bulk_create(days)
    home = anya.get("/pair/").content.decode()
    assert "Большое дерево" in home and "до гнезда" in home  # past the biggest stage the bar goes on, to what comes next
    assert 'data-time="' in home and 'class="lit"' in home and 'id="tree-night"' in home  # the sky follows the time of day
    assert "этап пары · 3 из 3" in home and "Откровенно" in home  # the stage sits in the tree card, a ribbon and a heart on it
    pair.refresh_from_db()
    assert set(pair.plan["tree"]) == {"big", "fruit"} and pair.plan["tree"]["fruit"][0] == today.isoformat()
    anya.get("/pair/")
    assert Pair.objects.get(id=pair.id).plan["tree"] == pair.plan["tree"]  # noted once, the day it appeared
    story = anya.get(f"/p/{pair.id}/story/").content.decode()
    assert "Выросло большое дерево" in story and "на вашем дереве" in story


def test_the_home_has_one_next_step_today_three_things_and_a_mood():
    from datetime import timedelta

    from django.urls import reverse

    from apps.compatibility.models import DailyAnswer

    anya, misha, stored = _linked_pair()
    pair = Pair.objects.get(id=stored.pair_id)
    today = timezone.localdate()
    days = [DailyAnswer(pair=pair, side=s, day=today - timedelta(days=n), question="q", text="ok") for n in range(1, 4) for s in "ab"]
    DailyAnswer.objects.bulk_create(days)
    for person in (pair.a, pair.b):  # both questionnaires done: the couple's path is behind them
        person.answers = person.answers or {"done": True}
        person.save(update_fields=["answers"])
    home = anya.get("/pair/").content.decode()
    assert "Вопрос дня ждёт вас" in home and 'aria-label="Путь пары' not in home  # the path is done: today's question is next
    assert "Думаю о тебе" in home and 'id="thanks"' in home and "погода пары" not in home  # the weather is in «Сегодня» now
    daily = anya.get("/daily/").content.decode()
    assert "три дела на сегодня" in daily and "Ещё на этой неделе" in daily and "Как вы сегодня?" in daily
    assert "Политика данных" in anya.get(reverse("account")).content.decode()  # the footer's links live in «Профиль»

    assert anya.post("/daily/mood/", {"mood": "rain"}).status_code == 400  # only the five
    assert anya.post("/daily/mood/", {"mood": "tired"}).json() == {"mood": "tired"}
    assert "Аня: устало" in misha.get("/pair/").content.decode() and "Аня: " in misha.get("/daily/").content.decode()
    anya.post("/daily/mood/", {"mood": ""})  # taken back
    assert "Аня: устало" not in misha.get("/pair/").content.decode()
    yesterday = (today - timedelta(days=1)).isoformat()
    Pair.objects.filter(id=pair.id).update(plan={**Pair.objects.get(id=pair.id).plan, "mood": {"a": [yesterday, "sad"]}})
    assert "Аня: грустно" not in misha.get("/pair/").content.decode()  # yesterday's mood is gone by morning
    assert Client().post("/daily/mood/", {"mood": "sun"}).status_code == 404
