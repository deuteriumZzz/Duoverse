"""Payments (ADR-0011): locks, YooKassa checkout with server-side status checks, «Пара+» shared with the partner."""

import re
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.compatibility.access import mark_paid, plus_for_pair, unlocked
from apps.compatibility.infrastructure import yookassa
from apps.compatibility.models import Purchase
from tests.test_flows import make_pair, sign_in

pytestmark = pytest.mark.django_db(transaction=True)


def test_free_report_shows_summary_and_locks_the_depth():
    client = Client()
    stored = make_pair(client)
    razbor = client.get(f"/r/{stored.id}/razbor/").content.decode()
    assert razbor.count("Полный разбор вашей пары") == len(stored.snapshot["spheres"]) - 1  # first sphere stays open
    assert "Что откроется для" in client.get(f"/r/{stored.id}/astrology/").content.decode()  # what this pair gets, by name
    assert "Что откроется для" in client.get(f"/r/{stored.id}/pdf/").content.decode()
    assert "Полный разбор вашей пары" not in client.get("/report/razbor/").content.decode()  # the demo stays a showcase


def test_test_checkout_unlocks_the_pair_for_both(settings):
    settings.DEBUG = True
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    code = re.search(r"/join/([A-Z0-9]{6})/", anya.get(f"/r/{stored.id}/invite/").content.decode()).group(1)
    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept", "consent": "on"})

    checkout = misha.post("/pay/deep/", {"pair": stored.pair.id})["Location"]  # the partner can pay too
    assert checkout.startswith("/pay/test/")
    result = misha.post(checkout, {"result": "ok"})
    assert "Готово, открыто" in misha.get(result["Location"]).content.decode()
    assert unlocked(stored.pair)
    assert "Полный разбор вашей пары" not in anya.get(f"/r/{stored.id}/razbor/").content.decode()


def test_yookassa_status_is_checked_server_side(settings, monkeypatch):
    settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY = "123", "test_key"
    created = {}

    def fake_create(purchase_id, amount, description, email, return_url):
        created.update(purchase_id=purchase_id, amount=amount, email=email)
        return "pay-1", "https://yoomoney.ru/checkout?orderId=pay-1"

    status = {"value": "pending"}
    monkeypatch.setattr(yookassa, "create_payment", fake_create)
    monkeypatch.setattr(yookassa, "payment_status", lambda pid: status["value"])
    client = Client()
    stored = make_pair(client, email="anya@example.com")
    assert client.post("/pay/deep/", {"pair": stored.pair.id})["Location"].startswith("https://yoomoney.ru/")
    assert created == {"purchase_id": str(Purchase.objects.get().id), "amount": 490, "email": "anya@example.com"}

    Client().post(
        "/yookassa/webhook/",
        {"type": "notification", "event": "payment.succeeded", "object": {"id": "pay-1"}},
        content_type="application/json",
    )
    assert not unlocked(stored.pair)  # the notification body alone proves nothing: YooKassa still says pending
    status["value"] = "succeeded"
    Client().post("/yookassa/webhook/", {"object": {"id": "pay-1"}}, content_type="application/json")
    assert unlocked(stored.pair)


def test_plus_stacks_and_only_the_year_opens_every_report_of_the_payer():
    client = Client()
    first = make_pair(client, email="anya@example.com")
    second = make_pair(client, email="anya@example.com")
    owner = first.pair.owner
    p1 = Purchase.objects.create(owner=owner, kind="plus", amount=249)
    mark_paid(p1)
    p2 = Purchase.objects.create(owner=owner, kind="plus", amount=249)
    mark_paid(p2)
    assert p2.valid_until - timezone.now() > timedelta(days=59)  # paying early never loses days
    assert plus_for_pair(first.pair) and not unlocked(first.pair)  # the month is the daily extras, never cheaper than the report
    mark_paid(Purchase.objects.create(owner=owner, kind="plus365", amount=1490))
    assert unlocked(first.pair) and unlocked(second.pair)  # a paid year opens every report of the payer


def test_quiz_of_the_week_is_plus_and_opens_after_both_answer():
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    code = re.search(r"/join/([A-Z0-9]{6})/", anya.get(f"/r/{stored.id}/invite/").content.decode()).group(1)
    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept", "consent": "on"})
    assert "Квиз недели — в «Паре+»" not in anya.get("/daily/quiz/").content.decode()  # the joining week of «Пара+» opens it
    Purchase.objects.filter(kind="trial").update(valid_until=timezone.now())  # the week is over
    assert "Квиз недели — в «Паре+»" in anya.get("/daily/quiz/").content.decode()

    mark_paid(Purchase.objects.create(owner=stored.pair.owner, kind="plus", amount=249))
    picks = {f"q{i}": "0" for i in range(6)}
    guesses = {f"g{i}": "0" for i in range(6)}  # what each thinks the other picked
    assert anya.post("/daily/quiz/", picks).status_code == 422  # with a partner, guessing is part of it
    anya.post("/daily/quiz/", {**picks, **guesses})
    assert "Ваши ответы сохранены" in anya.get("/daily/quiz/").content.decode()
    misha.post("/daily/quiz/", {**picks, "q5": "1", **guesses})  # Anya's «Пара+» covers Misha in the linked pair
    page = anya.get("/daily/quiz/").content.decode()
    assert "83%" in page and "Разные ответы" in page
    assert '5 <span class="text-ink-3">·</span> 6' in page  # Anya guessed 5 of Misha's 6, Misha guessed all of hers


def test_year_of_plus_and_a_week_when_the_partner_joins(settings):
    settings.DEBUG = True
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    code = re.search(r"/join/([A-Z0-9]{6})/", anya.get(f"/r/{stored.id}/invite/").content.decode()).group(1)
    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept", "consent": "on"})
    trial = Purchase.objects.get(kind="trial")  # the moment both see the value: a week of «Пара+» for the pair
    assert trial.owner == stored.pair.owner and plus_for_pair(stored.pair)
    assert not unlocked(stored.pair)  # the free week opens the extras, not the report
    assert "год «Пары+» за 1490 ₽" in anya.get(f"/r/{stored.id}/razbor/").content.decode()  # the lock offers both ways
    assert (trial.valid_until - timezone.now()).days in (6, 7)

    year = anya.post("/pay/plus365/")["Location"]
    anya.post(year, {"result": "ok"})
    paid = Purchase.objects.get(kind="plus365")
    assert paid.amount == 1490 and (paid.valid_until - trial.valid_until).days == 365  # stacks on the trial, no days lost
    assert unlocked(stored.pair)

    other = make_pair(anya, email="anya@example.com")
    from apps.compatibility.access import grant_trial

    assert grant_trial(other.pair) is False  # once per inviter, ever


def test_gift_is_bought_once_and_opens_someone_elses_pair(settings):
    settings.DEBUG = True
    giver = Client()
    make_pair(giver, email="giver@example.com")
    pay = giver.post("/pay/gift/")["Location"]
    done = giver.get(giver.post(pay, {"result": "ok"})["Location"]).content.decode()
    gift = Purchase.objects.get(kind="gift")
    assert gift.gift_code and gift.gift_code in done and f"/gift/{gift.gift_code}/" in done  # a code and a link to send

    assert "why=gift" in Client().get(f"/gift/{gift.gift_code}/").content.decode()  # the recipient signs in first
    them = Client()
    stored = make_pair(them, email="them@example.com")
    assert not unlocked(stored.pair)
    page = them.get(f"/gift/{gift.gift_code}/").content.decode()
    assert "Какую пару открыть" in page
    assert "Открыть подарком" in them.get(f"/r/{stored.id}/razbor/").content.decode()  # the gift waits on the report too
    them.post(f"/gift/{gift.gift_code}/", {"pair": stored.pair.id})
    assert unlocked(stored.pair)
    assert them.get(f"/gift/{gift.gift_code}/").status_code == 404  # used once
