"""Slice B: ephemeris adapter, synastry aspects, houses, dominant element."""

from datetime import date, time

from apps.astrology.domain.chart import ASPECTS, BirthData, Chart, Place, dominant_element, houses_overlay, score, synastry
from apps.astrology.infrastructure.ephemeris import CityGeocoder, SkyfieldEphemeris, _arc

eph, geo = SkyfieldEphemeris(), CityGeocoder()


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


GOLDEN = [  # Swiss Ephemeris 2.10 (Moshier) for the same births: planets, Ascendant, MC, 12 Placidus cusps
    (
        ("1996-03-14", "07:40", 59.9343, 30.3351, "Europe/Moscow"),
        {
            "Солнце": 353.887,
            "Луна": 283.407,
            "Меркурий": 341.258,
            "Венера": 38.933,
            "Марс": 351.837,
            "Юпитер": 283.782,
            "Сатурн": 357.026,
            "Уран": 303.346,
            "Нептун": 297.177,
            "Плутон": 243.096,
            "Северный узел": 197.342,
            "Лилит": 108.693,
            "Асцендент": 10.411,
            "MC": 272.218,
        },
        [10.411, 61.192, 79.082, 92.218, 105.847, 126.119, 190.411, 241.192, 259.082, 272.218, 285.847, 306.119],
    ),
    (
        ("1994-09-02", "23:15", 55.7963, 49.1088, "Europe/Moscow"),
        {
            "Солнце": 160.083,
            "Луна": 121.998,
            "Меркурий": 177.788,
            "Венера": 205.745,
            "Марс": 100.917,
            "Юпитер": 220.082,
            "Сатурн": 338.926,
            "Уран": 292.734,
            "Нептун": 290.81,
            "Плутон": 235.499,
            "Северный узел": 227.36,
            "Лилит": 46.495,
            "Асцендент": 89.258,
            "MC": 317.116,
        },
        [89.258, 103.747, 118.539, 137.116, 165.624, 215.486, 269.258, 283.747, 298.539, 317.116, 345.624, 35.486],
    ),
    (
        ("1997-08-09", "06:30", -8.112, 115.08818, "Asia/Makassar"),
        {
            "Солнце": 136.394,
            "Луна": 197.349,
            "Меркурий": 162.997,
            "Венера": 169.668,
            "Марс": 206.702,
            "Юпитер": 317.082,
            "Сатурн": 20.315,
            "Уран": 306.294,
            "Нептун": 298.074,
            "Плутон": 242.833,
            "Северный узел": 170.083,
            "Лилит": 165.835,
            "Асцендент": 135.205,
            "MC": 52.46,
        },
        [135.205, 168.718, 202.134, 232.46, 259.79, 286.418, 315.205, 348.718, 22.134, 52.46, 79.79, 106.418],
    ),
    (
        ("1901-05-20", "12:00", 51.5074, -0.1278, "Europe/London"),
        {
            "Солнце": 58.754,
            "Луна": 89.971,
            "Меркурий": 65.768,
            "Венера": 63.919,
            "Марс": 153.357,
            "Юпитер": 282.461,
            "Сатурн": 285.925,
            "Уран": 255.584,
            "Нептун": 87.818,
            "Плутон": 76.732,
            "Северный узел": 232.573,
            "Лилит": 210.672,
            "Асцендент": 157.008,
            "MC": 59.521,
        },
        [157.008, 177.857, 205.025, 239.521, 277.541, 310.541, 337.008, 357.857, 25.025, 59.521, 97.541, 130.541],
    ),
    (
        ("1958-12-31", "23:59", -33.8688, 151.2093, "Australia/Sydney"),
        {
            "Солнце": 279.394,
            "Луна": 165.457,
            "Меркурий": 257.143,
            "Венера": 291.514,
            "Марс": 47.377,
            "Юпитер": 233.896,
            "Сатурн": 269.42,
            "Уран": 135.686,
            "Нептун": 216.554,
            "Плутон": 154.076,
            "Северный узел": 198.342,
            "Лилит": 34.919,
            "Асцендент": 195.933,
            "MC": 99.602,
        },
        [195.933, 231.321, 257.035, 279.602, 303.592, 334.005, 15.933, 51.321, 77.035, 99.602, 123.592, 154.005],
    ),
    (
        ("1985-06-21", "04:10", 64.5401, 40.5433, "Europe/Moscow"),
        {
            "Солнце": 89.58,
            "Луна": 119.256,
            "Меркурий": 104.781,
            "Венера": 44.055,
            "Марс": 97.68,
            "Юпитер": 316.554,
            "Сатурн": 232.407,
            "Уран": 255.413,
            "Нептун": 272.316,
            "Плутон": 212.05,
            "Северный узел": 47.452,
            "Лилит": 32.131,
            "Асцендент": 103.058,
            "MC": 309.742,
        },
        [103.058, 109.409, 117.558, 129.742, 152.515, 212.801, 283.058, 289.409, 297.558, 309.742, 332.515, 32.801],
    ),
    (
        ("2009-02-28", "18:45", -23.5505, -46.6333, "America/Sao_Paulo"),
        {
            "Солнце": 340.443,
            "Луна": 26.733,
            "Меркурий": 318.044,
            "Венера": 14.79,
            "Марс": 318.864,
            "Юпитер": 312.656,
            "Сатурн": 169.008,
            "Уран": 351.914,
            "Нептун": 324.554,
            "Плутон": 272.978,
            "Северный узел": 308.893,
            "Лилит": 276.262,
            "Асцендент": 164.582,
            "MC": 79.387,
        },
        [164.582, 202.76, 233.667, 259.387, 283.766, 310.724, 344.582, 22.76, 53.667, 79.387, 103.766, 130.724],
    ),
    (
        ("2024-11-05", "09:05", 40.7128, -74.006, "America/New_York"),
        {
            "Солнце": 223.652,
            "Луна": 269.365,
            "Меркурий": 243.817,
            "Венера": 262.609,
            "Марс": 120.475,
            "Юпитер": 80.113,
            "Сатурн": 342.78,
            "Уран": 55.717,
            "Нептун": 357.419,
            "Плутон": 299.786,
            "Северный узел": 5.975,
            "Лилит": 194.31,
            "Асцендент": 253.199,
            "MC": 182.767,
        },
        [253.199, 287.297, 326.601, 2.767, 31.201, 53.644, 73.199, 107.297, 146.601, 182.767, 211.201, 233.644],
    ),
]


TOLERANCE = {"Северный узел": 0.05, "Лилит": 0.2}  # osculating node and Meeus' mean apogee; everything else to 0.01°


def test_skyfield_matches_swiss_ephemeris_reference():
    """Switching from Swiss Ephemeris (AGPL) to Skyfield + JPL DE421 must not move anything a reader would see."""
    for (day, at, lat, lon, tz), planets, houses in GOLDEN:
        c = eph.chart(BirthData(date.fromisoformat(day), time.fromisoformat(at), Place("x", lat, lon, tz)))
        for k, v in planets.items():
            assert abs(_arc(v, c.planets[k])) <= TOLERANCE.get(k, 0.01), (day, k, v, c.planets[k])
        assert all(abs(_arc(h, ch)) <= 0.01 for h, ch in zip(houses, c.houses or [], strict=True)), day


def test_polar_birth_falls_back_to_equal_quadrants():
    c = eph.chart(BirthData(date(1990, 6, 21), time(12, 0), Place("Норильск", 69.35, 88.2, "Asia/Krasnoyarsk")))
    assert c.houses and len(c.houses) == 12 and c.houses[0] == c.asc and c.houses[9] == c.mc


def test_chiron_comes_from_the_horizons_table_and_is_skipped_without_it(tmp_path, settings):
    from apps.astrology.infrastructure import ephemeris

    ephemeris._sky()  # DE421 stays where it is; only the Chiron table moves to tmp_path
    settings.EPHEMERIS_DIR = str(tmp_path)
    birth = BirthData(date(2000, 1, 1), None, None)  # noon UT, JD 2451545.0
    try:
        ephemeris._chiron.cache_clear()
        assert "Хирон" not in eph.chart(birth).planets
        rows = "# test\n2451544.5 251.5602909\n2451545.5 251.6745978\n2451546.5 251.7882564\n"  # JPL Horizons, 2000-01-01..03
        (tmp_path / "chiron.txt").write_text(rows)
        ephemeris._chiron.cache_clear()
        c = eph.chart(birth)
        assert abs(c.planets["Хирон"] - 251.617) < 0.01 and c.sign("Хирон") == "Стрелец" and c.speeds["Хирон"] > 0
        assert "Хирон" not in eph.chart(BirthData(date(2001, 1, 1), None, None)).planets  # outside the table
    finally:
        ephemeris._chiron.cache_clear()
