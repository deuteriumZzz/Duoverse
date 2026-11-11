"""Birthplaces anywhere on Earth: search in any spelling, map points, coordinates reaching the chart."""

import pytest
from django.test import Client

from apps.compatibility import places
from apps.compatibility.models import GeoPlace, Person, StoredReport
from tests.test_flows import sign_in

pytestmark = pytest.mark.django_db(transaction=True)


def add(gid, name, name_en, country, lat, lon, tz, pop):
    GeoPlace.objects.create(
        id=gid, name=name, name_en=name_en, country=country, lat=lat, lon=lon, tz=tz, population=pop,
        key=places.search_key(name), key_en=places.search_key(name_en),
    )  # fmt: skip


@pytest.fixture
def bali():
    add(1626932, "Сингараджа", "Singaraja", "ID", -8.112, 115.08818, "Asia/Makassar", 133784)
    add(1645528, "Денпасар", "Denpasar", "ID", -8.65, 115.21667, "Asia/Makassar", 834881)
    add(1880252, "Сингапур", "Singapore", "SG", 1.28967, 103.85007, "Asia/Singapore", 5638700)


def test_search_key_ignores_spelling_and_alphabet():
    assert places.search_key("Сингараджа") == places.search_key("Singaraja")
    assert places.search_key("Таллин") == places.search_key("Tallinn")
    assert places.search_key("Екатеринбург") == places.search_key("Yekaterinburg")


def test_search_near_and_box(bali, client):
    names = [p["name"] for p in client.get("/places/search/", {"q": "сингар"}).json()["items"]]
    assert names == ["Сингараджа"]
    assert [p["name"] for p in client.get("/places/search/", {"q": "Singa"}).json()["items"]] == ["Сингапур", "Сингараджа"]
    near = client.get("/places/near/", {"lat": "-8.2", "lon": "115.1"}).json()
    assert near["place"]["name"] == "Сингараджа" and near["km"] < 15
    assert [p["name"] for p in client.get("/places/box/", {"w": 114, "s": -9, "e": 116, "n": -7}).json()["items"]] == [
        "Денпасар",
        "Сингараджа",
    ]
    assert client.get("/places/near/", {"lat": "x", "lon": "1"}).json() == {"place": None}


def test_coords_are_validated_at_the_form_boundary():
    assert places.coords("-8.112", "115.088", "Asia/Makassar") == (-8.112, 115.088, "Asia/Makassar")
    assert places.coords("95", "0", "UTC") is None
    assert places.coords("1", "2", "Not/AZone") is None
    assert places.coords("nan", "2", "UTC") is None


def test_a_map_point_reaches_the_chart(bali):
    client = Client()
    sign_in(client)
    resp = client.post(
        "/new/",
        {"mode": "extended", "a_name": "Тася", "a_date": "1997-08-09", "a_time": "06:30", "a_place": "Сингараджа",
         "a_lat": "-8.112", "a_lon": "115.08818", "a_tz": "Asia/Makassar",
         "b_name": "Дима", "b_date": "1995-04-21", "b_time": "10:00", "b_place": "Денпасар"},
    )  # fmt: skip
    stored = StoredReport.objects.get(id=resp["Location"].split("r=")[1])
    a, b = Person.objects.get(id=stored.pair.a_id), Person.objects.get(id=stored.pair.b_id)
    assert a.birth["tz"] == "Asia/Makassar" and a.birth["lat"] == -8.112
    assert b.birth["tz"] == "Asia/Makassar"  # a typed name found in GeoNames gets its coordinates too
    stored.refresh_from_db()
    assert stored.snapshot["astrology"]["houses_available"] is True  # neither city is in the old 30-city list
