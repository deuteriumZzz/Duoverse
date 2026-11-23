"""Ephemeris adapter (ADR-0004): Skyfield (MIT) over NASA JPL DE421 (public domain) — no licence fees or source
obligations. Planets, true lunar node, mean Lilith, Placidus houses; Chiron is not computed."""

import math
from datetime import datetime, time
from functools import lru_cache
from zoneinfo import ZoneInfo

from apps.astrology.domain.chart import BirthData, Chart, Place

# ── Skyfield (MIT) over NASA JPL DE421 (public domain): no licence strings attached ─────────────
_SKY_BODIES = {
    "Солнце": "sun", "Луна": "moon", "Меркурий": "mercury", "Венера": "venus", "Марс": "mars",
    "Юпитер": "jupiter barycenter", "Сатурн": "saturn barycenter", "Уран": "uranus barycenter",
    "Нептун": "neptune barycenter", "Плутон": "pluto barycenter",
}  # fmt: skip
_STEP = 0.01  # days, for speeds by central difference


@lru_cache(maxsize=1)
def _sky():
    """Timescale and the DE421 kernel (1899–2053), downloaded once into EPHEMERIS_DIR if it is missing."""
    from django.conf import settings
    from skyfield.api import Loader

    loader = Loader(str(getattr(settings, "EPHEMERIS_DIR", "data")), verbose=False)
    return loader.timescale(builtin=True), loader("de421.bsp")


def _norm(x: float) -> float:
    return x % 360.0


def _arc(a: float, b: float) -> float:
    """Signed shortest difference b − a in degrees."""
    return (b - a + 180.0) % 360.0 - 180.0


def mean_lilith(jd_tt: float) -> float:
    """Mean lunar apogee (Black Moon Lilith): Meeus, Astronomical Algorithms, ch. 47 (mean perigee + 180°)."""
    t = (jd_tt - 2451545.0) / 36525.0
    perigee = 83.3532465 + 4069.0137287 * t - 0.0103200 * t**2 - t**3 / 80053 + t**4 / 18999000
    return _norm(perigee + 180.0)


def houses_placidus(ramc: float, eps: float, lat: float) -> tuple[list[float], float, float]:
    """12 cusps, Ascendant and MC. Placidus divides each point's semi-arc in thirds; beyond the polar circles,
    where some points never rise or set and Placidus is undefined, the quadrants are split evenly (Porphyry)."""
    r, e, f = math.radians(ramc), math.radians(eps), math.radians(lat)
    mc = _norm(math.degrees(math.atan2(math.sin(r), math.cos(r) * math.cos(e))))
    asc = _norm(math.degrees(math.atan2(math.cos(r), -(math.sin(r) * math.cos(e) + math.tan(f) * math.sin(e)))))

    def lon_of_ra(ra: float) -> float:
        a = math.radians(ra)
        return _norm(math.degrees(math.atan2(math.sin(a), math.cos(a) * math.cos(e))))

    def cusp(part: float, nocturnal: bool) -> float | None:
        ra = ramc + (180 if nocturnal else 0)
        lon = lon_of_ra(ra + (-1 if nocturnal else 1) * 30 * part * 3)  # first guess: equal division of the equator
        for _ in range(60):
            dec = math.asin(math.sin(e) * math.sin(math.radians(lon)))
            x = math.tan(f) * math.tan(dec)
            if abs(x) > 1:
                return None
            ad = math.degrees(math.asin(x))  # ascensional difference
            arc = (90 - ad) if nocturnal else (90 + ad)  # nocturnal / diurnal semi-arc
            new = lon_of_ra(ra - arc * part) if nocturnal else lon_of_ra(ra + arc * part)
            if abs(_arc(lon, new)) < 1e-9:
                return new
            lon = new
        return lon

    found = [cusp(1 / 3, False), cusp(2 / 3, False), cusp(2 / 3, True), cusp(1 / 3, True)]
    if all(x is not None for x in found):
        c11, c12, c2, c3 = (float(x) for x in found)  # type: ignore[arg-type]
    else:  # Porphyry: each quadrant split into equal thirds of ecliptic longitude
        q1, q4 = (mc + 180 - asc) % 360, (asc - mc) % 360
        c2, c3 = _norm(asc + q1 / 3), _norm(asc + 2 * q1 / 3)
        c11, c12 = _norm(mc + q4 / 3), _norm(mc + 2 * q4 / 3)
    opposite = [_norm(x + 180) for x in (mc, c11, c12, asc, c2, c3)]
    cusps = [asc, c2, c3, *opposite[:3], *opposite[3:], mc, c11, c12]
    return cusps, asc, mc


class SkyfieldEphemeris:
    """Tropical geocentric positions of date (apparent, true equinox) like the astrology standard."""

    def chart(self, birth: BirthData) -> Chart:
        from skyfield.framelib import ecliptic_frame
        from skyfield.nutationlib import mean_obliquity

        ts, eph = _sky()
        exact = birth.time is not None and birth.place is not None
        local = datetime.combine(birth.day, birth.time or time(12, 0))
        tz = ZoneInfo(birth.place.tz) if birth.place else ZoneInfo("UTC")
        ut = local.replace(tzinfo=tz).astimezone(ZoneInfo("UTC"))
        # civil time is read as UT1 (mean solar time): before 1972 there was no UTC with leap seconds, and since then
        # the two differ by under a second; reading 1900 dates through modern UTC would shift the houses by ~0.2°
        t = ts.ut1(ut.year, ut.month, ut.day, ut.hour, ut.minute, ut.second)
        span = ts.tt_jd([t.tt - _STEP, t.tt, t.tt + _STEP])
        earth = eph["earth"]
        planets, speeds = {}, {}
        for name, target in _SKY_BODIES.items():
            _, lon, _ = earth.at(span).observe(eph[target]).apparent().frame_latlon(ecliptic_frame)
            d = lon.degrees
            planets[name], speeds[name] = round(float(d[1]), 3), round(_arc(d[0], d[2]) / (2 * _STEP), 4)
        # true (osculating) lunar node: the line where the Moon's momentary orbit crosses the ecliptic
        nodes = []
        for i in range(3):
            pos, vel = (eph["moon"] - earth).at(span[i]).frame_xyz_and_velocity(ecliptic_frame)
            r, v = pos.au, vel.au_per_d
            h = (r[1] * v[2] - r[2] * v[1], r[2] * v[0] - r[0] * v[2], r[0] * v[1] - r[1] * v[0])
            nodes.append(_norm(math.degrees(math.atan2(h[0], -h[1]))))
        planets["Северный узел"], speeds["Северный узел"] = round(nodes[1], 3), round(_arc(nodes[0], nodes[2]) / (2 * _STEP), 4)
        lil = [mean_lilith(x) for x in (t.tt - _STEP, t.tt, t.tt + _STEP)]
        planets["Лилит"], speeds["Лилит"] = round(lil[1], 3), round(_arc(lil[0], lil[2]) / (2 * _STEP), 4)
        if not exact or birth.place is None:
            return Chart(planets, exact_time=False, speeds=speeds)
        _, d_eps = t._nutation_angles_radians
        eps = mean_obliquity(t.tdb) / 3600.0 + math.degrees(d_eps)
        ramc = _norm(t.gast * 15.0 + birth.place.lon)
        cusps, asc, mc = houses_placidus(ramc, eps, birth.place.lat)
        planets["Асцендент"], planets["MC"] = round(asc, 3), round(mc, 3)
        return Chart(planets, exact_time=True, houses=[round(c, 3) for c in cusps], asc=round(asc, 3), mc=round(mc, 3), speeds=speeds)


CITIES = {
    "Москва": (55.7558, 37.6173, "Europe/Moscow"),
    "Санкт-Петербург": (59.9343, 30.3351, "Europe/Moscow"),
    "Новосибирск": (55.0084, 82.9357, "Asia/Novosibirsk"),
    "Екатеринбург": (56.8389, 60.6057, "Asia/Yekaterinburg"),
    "Казань": (55.7963, 49.1088, "Europe/Moscow"),
    "Нижний Новгород": (56.2965, 43.9361, "Europe/Moscow"),
    "Челябинск": (55.1644, 61.4368, "Asia/Yekaterinburg"),
    "Самара": (53.1959, 50.1002, "Europe/Samara"),
    "Омск": (54.9885, 73.3242, "Asia/Omsk"),
    "Ростов-на-Дону": (47.2357, 39.7015, "Europe/Moscow"),
    "Уфа": (54.7388, 55.9721, "Asia/Yekaterinburg"),
    "Красноярск": (56.0153, 92.8932, "Asia/Krasnoyarsk"),
    "Воронеж": (51.672, 39.1843, "Europe/Moscow"),
    "Пермь": (58.0105, 56.2502, "Asia/Yekaterinburg"),
    "Волгоград": (48.708, 44.5133, "Europe/Volgograd"),
    "Краснодар": (45.0355, 38.9753, "Europe/Moscow"),
    "Сочи": (43.6028, 39.7342, "Europe/Moscow"),
    "Иркутск": (52.2869, 104.305, "Asia/Irkutsk"),
    "Хабаровск": (48.4802, 135.0719, "Asia/Vladivostok"),
    "Владивосток": (43.1155, 131.8855, "Asia/Vladivostok"),
    "Калининград": (54.7104, 20.4522, "Europe/Kaliningrad"),
    "Минск": (53.9006, 27.559, "Europe/Minsk"),
    "Киев": (50.4501, 30.5234, "Europe/Kyiv"),
    "Алматы": (43.222, 76.8512, "Asia/Almaty"),
    "Астана": (51.1694, 71.4491, "Asia/Almaty"),
    "Ташкент": (41.2995, 69.2401, "Asia/Tashkent"),
    "Тбилиси": (41.7151, 44.8271, "Asia/Tbilisi"),
    "Ереван": (40.1792, 44.4991, "Asia/Yerevan"),
    "Берлин": (52.52, 13.405, "Europe/Berlin"),
    "Лондон": (51.5074, -0.1278, "Europe/London"),
    "Нью-Йорк": (40.7128, -74.006, "America/New_York"),
}


class CityGeocoder:
    """Offline table of the most common birthplaces. # ponytail: swap for a geocoding API adapter when users need any town."""

    def lookup(self, name: str) -> Place | None:
        key = next((c for c in CITIES if c.lower() == (name or "").strip().lower()), None)
        return Place(key, *CITIES[key]) if key else None

    def names(self) -> list[str]:
        return list(CITIES)
