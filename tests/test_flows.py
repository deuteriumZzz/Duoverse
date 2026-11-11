"""End-to-end flows over the database: no fixtures, every report is computed."""

import json
import re

import pytest
from django.core import mail
from django.test import Client

from apps.compatibility.infrastructure.demo import answers_for
from apps.compatibility.models import Owner, Person, StoredReport
from apps.knowledge.models import KnowledgeBlock

pytestmark = pytest.mark.django_db(transaction=True)  # on_commit hooks fire, Celery runs eagerly

TABS = ["", "astrology/", "psychology/", "numbers/", "tarot/", "habits/", "share/", "pdf/", "weights/", "razbor/"]


def sign_in(client: Client, email: str = "anya@example.com", next_url: str = "") -> str:
    """Email-code sign-in as a person would do it; returns where the app sends them next."""
    from django.core.cache import cache

    from apps.compatibility.services import email_hash

    mail.outbox.clear()
    cache.delete(f"login-sent:{email_hash(email)}")  # tests sign in faster than the 45 s resend pause
    client.post("/login/", {"email": email, "next": next_url})
    code = re.search(r"Ваш код: (\d{6})", mail.outbox[-1].body).group(1)
    resp = client.post("/login/code/", {"code": code, "next": next_url})
    assert resp.status_code == 302, resp
    return resp["Location"]


def make_pair(client: Client, mode: str = "extended", email: str = "anya@example.com") -> StoredReport:
    resp = client.post(
        "/new/",
        {
            "mode": mode,
            "a_name": "Аня",
            "a_date": "1996-03-14",
            "a_time": "07:40",
            "a_place": "Санкт-Петербург",
            "b_name": "Миша",
            "b_date": "1994-09-02",
            "b_time": "23:15",
            "b_place": "Казань",
        },
    )
    assert resp.status_code == 302
    location = resp["Location"]
    if location.startswith("/login/"):
        from urllib.parse import parse_qs, urlparse

        location = sign_in(client, email, parse_qs(urlparse(location).query)["next"][0])
    if mode == "deep":
        resp["Location"] = location
        return resp
    rid = location.split("r=")[1]
    return StoredReport.objects.get(id=rid)


def test_wizard_creates_encrypted_people_and_a_ready_report():
    client = Client()
    stored = make_pair(client)
    stored.refresh_from_db()
    assert stored.status == "ready" and stored.snapshot["total_score"] > 0
    raw = Person.objects.raw("SELECT id, birth FROM compatibility_person LIMIT 1")[0].__dict__
    assert "1996" not in str(Person.objects.values_list("birth", flat=True).query) and raw  # birth stored encrypted
    for tab in TABS:
        assert client.get(f"/r/{stored.id}/{tab}").status_code == 200, tab
    assert client.get(f"/r/{stored.id}/share/card.svg")["Content-Type"].startswith("image/svg")


def test_generation_status_redirects_to_stored_report():
    client = Client()
    stored = make_pair(client)
    done = client.get(f"/generating/status/?step=99&r={stored.id}")
    assert done["HX-Redirect"] == f"/r/{stored.id}/?reveal=1"


def test_other_devices_cannot_open_a_report():
    stored = make_pair(Client())
    assert Client().get(f"/r/{stored.id}/").status_code == 404


def test_identical_inputs_reuse_the_snapshot():
    client = Client()
    stored = make_pair(client)
    from apps.compatibility.services import request_report

    assert request_report(stored.pair).id == stored.id


def test_quiz_answers_are_saved_and_unlock_psychology():
    client = Client()
    resp = make_pair(client, mode="deep")
    pid = re.search(r"/quiz/([0-9a-f-]+)/", resp["Location"]).group(1)
    assert client.get(f"/quiz/{pid}/").status_code == 200
    assert client.post(f"/quiz/{pid}/", {"answers": json.dumps({"e1": 3})}).status_code == 422  # incomplete
    resp = client.post(f"/quiz/{pid}/", {"answers": json.dumps(answers_for("anya"))})
    assert "/invite/" in resp["Location"]  # deep mode: partner answers next
    person = Person.objects.get(id=pid)
    assert person.answers["e1"] == answers_for("anya")["e1"]

    pair = person.owner.pairs.first()
    invite_page = client.get(resp["Location"]).content.decode()
    code = re.search(r"/join/([A-Z0-9]{6})/", invite_page).group(1)
    partner = Client()  # another phone
    assert "Войти по почте" in partner.get(f"/join/{code}/").content.decode()
    sign_in(partner, "misha@example.com")
    assert "Отметьте галочку" in partner.post(f"/join/{code}/", {"action": "accept"}).content.decode()  # 18+ and consent first
    assert pair.partner_id is None
    assert partner.post(f"/join/{code}/", {"action": "accept", "consent": "on"}).status_code == 302
    assert partner.post(f"/join/{code}/", {"answers": json.dumps(answers_for("misha"))}).status_code == 302
    status = client.get(f"/p/{pair.id}/status/")
    rid = status["Location"].split("r=")[1]
    report = StoredReport.objects.get(id=rid)
    assert report.snapshot["psychology"]["available"] is True
    assert report.snapshot["accuracy"]["value"] == 94  # 46 + 14 + 14 (time and place) + 20 (both questionnaires)


def test_public_share_link_shows_only_the_card():
    client = Client()
    stored = make_pair(client)
    page = client.get(f"/r/{stored.id}/share/").content.decode()
    token = re.search(r"/s/([^/'\"]+)/", page).group(1)
    public = Client().get(f"/s/{token}/").content.decode()
    assert stored.snapshot["pair_type"]["name"] in public and "1996" not in public
    assert Client().get("/s/forged-token/").status_code == 404


def test_export_magic_link_and_delete_everything():
    client = Client()
    stored = make_pair(client)
    export = json.loads(client.get("/account/export/").content)
    assert export["people"][0]["birth"]["date"] == "1996-03-14" and len(export["reports"]) == 1

    other_device = Client()
    sign_in(other_device, "anya@example.com")  # same account on a second phone
    assert other_device.get(f"/r/{stored.id}/").status_code == 200

    client.post("/account/delete/")
    assert not Owner.objects.exists() and not Person.objects.exists() and not StoredReport.objects.exists()


def test_history_and_profiles_list_owner_data():
    client = Client()
    make_pair(client)
    assert "Аня и Миша" in client.get("/history/").content.decode()
    profiles = client.get("/profiles/").content.decode()
    pid = re.search(r"/profiles/([0-9a-f-]+)/", profiles).group(1)
    resp = client.post(f"/profiles/{pid}/", {"name": "Анна", "date": "1996-03-14", "time": "07:40", "place": "Москва"})
    assert resp.status_code == 302 and Person.objects.get(id=pid).birth["place"] == "Москва"


def test_report_text_comes_from_knowledge_blocks():
    client = Client()
    stored = make_pair(client)
    keys = stored.snapshot["kb_keys"]
    assert any(k.startswith("SPHERE:") for k in keys) and any(k.startswith("CAT:") for k in keys)
    assert len(stored.snapshot["spheres"]) == 13
    assert KnowledgeBlock.objects.filter(key__in=keys).count() == len(keys)


def test_demo_razbor_shows_cross_layer_factors_and_depth(client):
    html = client.get("/report/razbor/").content.decode()
    assert "Точность разбора" in html and "Из чего это складывается у вас" in html and "18+" in html
    astro = client.get("/report/astrology/").content.decode()
    assert "<svg" in astro and "Наложение домов".lower() in astro.lower()


def test_report_nav_hides_layers_behind_one_tab_and_factors_link_into_them(client):
    overview = client.get("/report/").content.decode()
    assert "Из чего сложилось" in overview and "Точность разбора" in overview and 'href="/report/astrology/"' in overview
    layers = client.get("/report/layers/").content.decode()
    assert all(f'href="/report/{t}/"' in layers for t in ("astrology", "psychology", "numbers", "tarot"))
    astro = client.get("/report/astrology/").content.decode()
    assert "Все слои" in astro and 'id="asp-' in astro
    razbor = client.get("/report/razbor/").content.decode()
    assert 'href="/report/astrology/#asp-' in razbor and "Венера (Аня)" not in razbor


@pytest.mark.parametrize("url", ["/privacy/", "/consent/", "/terms/"])
def test_legal_pages_render_from_docs(client, url):
    body = client.get(url).content.decode()
    assert "<table" in body or "<h2" in body
    assert "fonts.googleapis" not in body


def test_making_a_pair_more_precise_keeps_the_data_and_the_pair():
    client = Client()
    sign_in(client)
    resp = client.post("/new/", {"mode": "quick", "a_name": "Аня", "a_date": "1996-03-14", "b_name": "Миша", "b_date": "1994-09-02"})
    stored = StoredReport.objects.get(id=resp["Location"].split("r=")[1])
    pair = stored.pair
    page = client.get(f"/r/{stored.id}/").content.decode()
    assert f"pair={pair.id}" in page  # «add time and place» comes back to this pair
    wizard = client.get(f"/new/?mode=extended&pair={pair.id}").content.decode()
    assert "1996-03-14" in wizard and "Аня" in wizard and "Ваши данные уже здесь" in wizard
    stranger = Client().get(f"/new/?pair={pair.id}").content.decode()
    assert "1996-03-14" not in stranger
    resp = client.post(
        "/new/",
        {
            "mode": "extended",
            "pair": str(pair.id),
            "a_name": "Аня",
            "a_date": "1996-03-14",
            "a_time": "07:40",
            "a_place": "Казань",
            "b_name": "Миша",
            "b_date": "1994-09-02",
        },
    )
    assert resp.status_code == 302
    pair.refresh_from_db()
    pair.a.refresh_from_db()
    assert pair.mode == "extended" and pair.a.birth["time"] == "07:40" and pair.a.birth["place"] == "Казань"
    assert pair.owner.pairs.count() == 1  # no duplicate pair


def test_quick_check_dates_carry_into_the_wizard(client):
    client.post("/start/result/", {"date_a": "1991-05-20", "date_b": "1993-12-01"})
    page = client.get("/new/?mode=extended").content.decode()
    assert "1991-05-20" in page and "1993-12-01" in page
