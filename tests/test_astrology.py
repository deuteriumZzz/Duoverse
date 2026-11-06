"""Slice B: ephemeris adapter, synastry aspects, houses, dominant element."""

from datetime import date, time

from apps.astrology.domain.chart import ASPECTS, BirthData, Chart, dominant_element, houses_overlay, score, synastry
from apps.astrology.infrastructure.ephemeris import CityGeocoder, SwissEphemeris

eph, geo = SwissEphemeris(), CityGeocoder()


def anya() -> Chart:
    return eph.chart(BirthData(date(1996, 3, 14), time(7, 40), geo.lookup("Санкт-Петербург")))


def test_sun_position_matches_ephemeris():
    c = anya()
    assert 353 < c.planets["Солнце"] < 355 and c.sign("Солнце") == "Рыбы"
    assert c.houses and len(c.houses) == 12 and c.asc is not None


def test_no_time_means_no_houses():
    c = eph.chart(BirthData(date(1996, 3, 14)))
    assert not c.exact_time and c.houses is None


def test_geocoder_is_case_insensitive_and_knows_timezones():
    assert geo.lookup("казань").tz == "Europe/Moscow"
    assert geo.lookup("Атлантида") is None


def _chart(**lons: float) -> Chart:
    base = dict.fromkeys(["Солнце", "Луна", "Меркурий", "Венера", "Марс", "Юпитер", "Сатурн"], 0.0)
    spread = {k: i * 47.0 for i, k in enumerate(base)}  # keep unrelated planets out of orb
    return Chart({**spread, **lons}, exact_time=True)


def test_trine_within_orb_is_found_and_harmonious():
    a, b = _chart(Венера=10.0), _chart(Марс=132.0)
    hit = next(h for h in synastry(a, b) if (h.planet_a, h.planet_b) == ("Венера", "Марс"))
    assert hit.kind.key == "trine" and hit.orb == 2.0 and hit.tone == "synergy"


def test_square_is_tension():
    a, b = _chart(Меркурий=0.0), _chart(Меркурий=91.0)
    hit = next(h for h in synastry(a, b) if (h.planet_a, h.planet_b) == ("Меркурий", "Меркурий"))
    assert hit.kind.key == "square" and hit.tone == "attention"


def test_orbs_cover_every_aspect_kind():
    assert {k.key for k in ASPECTS if k.major} == {"conj", "sextile", "square", "trine", "opp"}
    assert {k.key for k in ASPECTS if not k.major} == {"semisextile", "semisquare", "sesquiquadrate", "quincunx"}


def test_houses_overlay_and_score_bounds():
    a = anya()
    b = eph.chart(BirthData(date(1994, 9, 2), time(23, 15), geo.lookup("Казань")))
    ov = houses_overlay(a, b, "Ани", "Миши")
    r = score(a, b, synastry(a, b), ov)
    assert 0 <= r.score <= 100 and r.confidence == 92
    assert all(25 <= v <= 94 for v in r.categories.values())
    assert ov.lines  # someone's Moon or Venus lands in the other's 1/4/5/7 house


def test_dominant_element_breaks_ties_by_sun():
    assert dominant_element(anya()) == "water"


def test_midpoint_takes_the_short_arc_across_aries():
    from apps.astrology.domain.chart import _midpoint

    assert _midpoint(350.0, 10.0) == 0.0 and _midpoint(10.0, 350.0) == 0.0 and _midpoint(0.0, 90.0) == 45.0


def test_composite_planets_are_midpoints_and_houses_need_both_times():
    from apps.astrology.domain.chart import composite

    a, b = anya(), eph.chart(BirthData(date(1994, 9, 2), time(18, 5), geo.lookup("Москва")))
    comp = composite(a, b)
    assert comp.houses and len(comp.houses) == 12
    sun = comp.planets["Солнце"]
    assert min(abs(sun - a.planets["Солнце"]), 360 - abs(sun - a.planets["Солнце"])) <= 90
    assert composite(a, eph.chart(BirthData(date(1994, 9, 2)))).houses is None


def test_balance_percentages_add_up():
    from apps.astrology.domain.chart import balance

    bal = balance(anya())
    assert 98 <= sum(bal.elements.values()) <= 102 and 98 <= sum(bal.modalities.values()) <= 102


def test_double_whammy_is_marked_both_ways():
    a, b = _chart(Венера=10.0, Марс=200.0), _chart(Марс=12.0, Венера=202.0)
    doubles = {(h.planet_a, h.planet_b) for h in synastry(a, b) if h.double}
    assert {("Венера", "Марс"), ("Марс", "Венера")} <= doubles


def test_overlay_runs_in_both_directions_and_feeds_spheres():
    from apps.astrology.domain.chart import sphere_effects

    a, b = anya(), eph.chart(BirthData(date(1994, 9, 2), time(18, 5), geo.lookup("Москва")))
    ov = houses_overlay(a, b, "Аня", "Миша")
    assert {o.owner for o in ov.hits} == {"a", "b"}
    assert any(sphere_effects(synastry(a, b), ov).values())
