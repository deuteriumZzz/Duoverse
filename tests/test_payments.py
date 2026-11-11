"""Payments (ADR-0011): locks, YooKassa checkout with server-side status checks, «Пара+» shared with the partner."""

import re
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.compatibility.access import mark_paid, unlocked
from apps.compatibility.infrastructure import yookassa
from apps.compatibility.models import Purchase
from tests.test_flows import make_pair, sign_in

pytestmark = pytest.mark.django_db(transaction=True)


def test_free_report_shows_summary_and_locks_the_depth():
    client = Client()
    stored = make_pair(client)
    razbor = client.get(f"/r/{stored.id}/razbor/").content.decode()
    assert razbor.count("Полный разбор вашей пары") == len(stored.snapshot["spheres"]) - 1  # first sphere stays open
    assert "Полный разбор вашей пары" in client.get(f"/r/{stored.id}/astrology/").content.decode()
    assert "Полный разбор вашей пары" in client.get(f"/r/{stored.id}/pdf/").content.decode()
    assert "Полный разбор вашей пары" not in client.get("/report/razbor/").content.decode()  # the demo stays a showcase


def test_test_checkout_unlocks_the_pair_for_both(settings):
    settings.DEBUG = True
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    code = re.search(r"/join/([A-Z0-9]{6})/", anya.get(f"/r/{stored.id}/invite/").content.decode()).group(1)
    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept"})

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


def test_plus_stacks_and_covers_every_pair_of_the_payer():
    client = Client()
    first = make_pair(client, email="anya@example.com")
    second = make_pair(client, email="anya@example.com")
    owner = first.pair.owner
    p1 = Purchase.objects.create(owner=owner, kind="plus", amount=249)
    mark_paid(p1)
    p2 = Purchase.objects.create(owner=owner, kind="plus", amount=249)
    mark_paid(p2)
    assert unlocked(first.pair) and unlocked(second.pair)
    assert p2.valid_until - timezone.now() > timedelta(days=59)  # paying early never loses days


def test_quiz_of_the_week_is_plus_and_opens_after_both_answer():
    anya = Client()
    stored = make_pair(anya, email="anya@example.com")
    code = re.search(r"/join/([A-Z0-9]{6})/", anya.get(f"/r/{stored.id}/invite/").content.decode()).group(1)
    misha = Client()
    sign_in(misha, "misha@example.com")
    misha.post(f"/join/{code}/", {"action": "accept"})
    assert "Квизы — в «Паре+»" in anya.get("/daily/quiz/").content.decode()

    mark_paid(Purchase.objects.create(owner=stored.pair.owner, kind="plus", amount=249))
    picks = {f"q{i}": "0" for i in range(6)}
    anya.post("/daily/quiz/", picks)
    assert "Ваши ответы сохранены" in anya.get("/daily/quiz/").content.decode()
    misha.post("/daily/quiz/", {**picks, "q5": "1"})  # Anya's «Пара+» covers Misha in the linked pair
    page = anya.get("/daily/quiz/").content.decode()
    assert "83%" in page and "Разные ответы" in page
