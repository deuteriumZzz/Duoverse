"""Smoke checks for the clickable prototype: every screen renders, no dead internal links, all scenarios work."""

import re

import pytest
from django.test import Client
from django.urls import reverse

from apps.compatibility.infrastructure.demo import SCENARIOS
from apps.compatibility.infrastructure.engine_report_provider import STEPS
from apps.compatibility.models import StoredReport
from apps.tarot.domain.tarot import reduce22 as reduce_arcana

SCREENS = [
    "/",
    "/start/",
    "/new/",
    "/new/?mode=deep",
    "/quiz/",
    "/weights/",
    "/generating/",
    "/report/",
    "/report/share/",
    "/report/pdf/",
    "/pair/",
    "/pair/waiting/",
    "/pair/ready/",
    "/daily/",
    "/history/",
    "/profiles/",
    "/pricing/",
    "/account/",
    "/states/",
    "/disclaimer/",
    "/offline/",
    *[f"/report/{t}/" for t in ("astrology", "psychology", "numbers", "tarot", "habits", "layers", "razbor")],
]
pytestmark = pytest.mark.django_db

HREF = re.compile(r'href="(/[^"#]*)')


@pytest.fixture
def client() -> Client:
    return Client()


def use(client: Client, scenario: str) -> None:
    client.get(reverse("set_scenario", args=[scenario]))


@pytest.mark.parametrize("url", SCREENS)
def test_screen_renders(client, url):
    assert client.get(url).status_code == 200


def test_no_dead_internal_links(client):
    seen, queue = set(), list(SCREENS)
    while queue:
        url = queue.pop()
        if url in seen or url.startswith(("/static/", "/demo/", "/this-page-does-not-exist", "/account/export")) or url.endswith(".svg"):
            continue
        seen.add(url)
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
        queue += HREF.findall(resp.content.decode())
    assert len(seen) >= len(SCREENS)


@pytest.mark.parametrize("scenario", [s.key for s in SCENARIOS if s.key != "error"])
@pytest.mark.parametrize("tab", ["", "astrology/", "psychology/", "numbers/", "tarot/", "habits/", "layers/", "share/", "pdf/"])
def test_every_scenario_renders_every_tab(client, scenario, tab):
    use(client, scenario)
    assert client.get(f"/report/{tab}").status_code == 200


def test_error_scenario_shows_error_state(client):
    use(client, "error")
    resp = client.get("/report/")
    assert resp.status_code == 503 and "Не получилось собрать отчёт" in resp.content.decode()


def test_missing_data_is_disclosed(client):
    use(client, "dates_only")
    body = client.get("/report/").content.decode()
    assert "Точность разбора" in body and 'aria-valuenow="46"' in body and "Сделать точнее" in body


def test_quick_result_and_validation(client):
    ok = client.post("/start/result/", {"date_a": "1996-03-14", "date_b": "1994-09-02"}).content.decode()
    assert "Справедливость" in ok and "Повешенный" in ok and "Маг" in ok
    bad = client.post("/start/result/", {"date_a": "2999-01-01", "date_b": ""}).content.decode()
    assert "Проверьте даты" in bad


def test_generation_polling_redirects_to_report(client):
    steps = len(STEPS)
    assert client.get(f"/generating/status/?step={steps - 1}").status_code == 200
    done = client.get(f"/generating/status/?step={steps}")
    assert done.status_code == 204 and done["HX-Redirect"] == "/report/?reveal=1"


def test_wizard_requires_dates(client):
    assert client.post("/new/", {"a_date": "", "b_date": "1994-09-02"}).status_code == 422
    location = client.post("/new/", {"a_date": "1996-03-14", "b_date": "1994-09-02"})["Location"]
    assert location.startswith("/generating/?r=") and location.endswith("&save=1")  # data first, then the save sheet over it
    page = client.get(location).content.decode()
    assert "login-open" in page and "login-sheet-body" in page
    rid = location.split("r=")[1].split("&")[0]
    StoredReport.objects.filter(id=rid).update(status="ready")
    ready = client.get(f"/generating/status/?step=99&r={rid}")
    assert ready.status_code == 200 and "Сохранить и открыть" in ready.content.decode()  # no account: wait for the save, no redirect
    sheet = client.get("/login/", {"sheet": "1", "why": "save", "next": "/generating/?r=" + rid}).content.decode()
    assert "Сохраните разбор" in sheet and "<html" not in sheet  # just the card, for the panel


def test_scenario_switch_rejects_open_redirect(client):
    assert client.get("/demo/scenario/ideal/?next=https://evil.example")["Location"] == "/"


def test_share_card_downloads_as_svg(client):
    resp = client.get("/report/share/card.svg")
    assert resp.status_code == 200 and resp["Content-Type"].startswith("image/svg+xml")
    assert "attachment" in resp["Content-Disposition"] and "Парус и компас" in resp.content.decode()


def test_unknown_page_is_404(client):
    assert client.get("/nope/").status_code == 404


def test_pair_typology_has_78_pair_types():
    from apps.compatibility.domain.archetypes import ROLES, dynamic_for, pair_name
    from apps.web.templatetags.art import pair_poster_svg

    names = {pair_name(a, b) for a in ROLES.values() for b in ROLES.values()}
    assert len(names) == 144  # ordered: «Парус и компас» ≠ «Компас и парус»
    assert len({frozenset((a, b)) for a in ROLES for b in ROLES}) == 78
    assert {dynamic_for(a, b).key for a in ROLES.values() for b in ROLES.values()} == {"resonance", "complement", "contrast", "friction"}
    assert pair_poster_svg("sail", "compass") != pair_poster_svg("compass", "sail")


def test_quick_result_roles_come_from_dates(client):
    body = client.post("/start/result/", {"date_a": "1996-03-14", "date_b": "1994-09-02"}).content.decode()
    assert (
        "Парус и компас" in body
        and "стихии «вода» (Солнце в знаке Рыбы)" in body
        and "число пути 7 → инициатор" in body
        and "число пути 33 → проводник" in body
    )


def test_arcana_reduction():
    assert [reduce_arcana(n) for n in (1, 22, 23, 33, 44, 45)] == [1, 22, 1, 11, 22, 1]


def test_report_numerology_is_computed_not_fixture(client):
    body = client.get("/report/numbers/").content.decode()
    assert 'data-roll="33"' in body and 'data-roll="7"' in body  # Аня 33 (master), Миша 7


@pytest.mark.django_db
def test_healthz(client):
    assert client.get("/healthz").content == b"ok"


def test_dev_screens_are_hidden_in_production(client, settings):
    settings.DEV_SCREENS = False
    assert client.get("/states/").status_code == 404
    assert client.get("/demo/scenario/complex/").status_code == 404
    assert "Состояния интерфейса" not in client.get("/").content.decode()


def test_error_emails_mask_what_people_typed(rf):
    from django.views.debug import ExceptionReporter

    request = rf.post("/new/", {"birth_date": "1994-03-12", "name": "Аня"})
    text = ExceptionReporter(request, ValueError, ValueError("x"), None).get_traceback_text()
    assert "1994-03-12" not in text and "Аня" not in text
