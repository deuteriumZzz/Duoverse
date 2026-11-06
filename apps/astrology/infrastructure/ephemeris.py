"""Swiss Ephemeris adapter (ADR-0004). Built-in Moshier model covers the planets, nodes and Lilith;
Chiron needs the asteroid file `seas_18.se1` in EPHE_PATH and is simply omitted without it."""

import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

import swisseph as swe

from apps.astrology.domain.chart import BirthData, Chart, Place

_IDS = {
    "Солнце": swe.SUN,
    "Луна": swe.MOON,
    "Меркурий": swe.MERCURY,
    "Венера": swe.VENUS,
    "Марс": swe.MARS,
    "Юпитер": swe.JUPITER,
    "Сатурн": swe.SATURN,
    "Уран": swe.URANUS,
    "Нептун": swe.NEPTUNE,
    "Плутон": swe.PLUTO,
    "Северный узел": swe.TRUE_NODE,
    "Лилит": swe.MEAN_APOG,
}
EPHE_PATH = os.environ.get("SE_EPHE_PATH", "")
if EPHE_PATH:
    swe.set_ephe_path(EPHE_PATH)


class SwissEphemeris:
    def chart(self, birth: BirthData) -> Chart:
        exact = birth.time is not None and birth.place is not None
        local = datetime.combine(birth.day, birth.time or time(12, 0))
        tz = ZoneInfo(birth.place.tz) if birth.place else ZoneInfo("UTC")
        ut = local.replace(tzinfo=tz).astimezone(ZoneInfo("UTC"))
        jd = swe.julday(ut.year, ut.month, ut.day, ut.hour + ut.minute / 60 + ut.second / 3600)
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED if EPHE_PATH else swe.FLG_MOSEPH | swe.FLG_SPEED
        planets, speeds = {}, {}
        for name, pid in _IDS.items():
            pos = swe.calc_ut(jd, pid, flags)[0]
            planets[name], speeds[name] = round(pos[0], 3), round(pos[3], 4)
        if EPHE_PATH:
            try:
                pos = swe.calc_ut(jd, swe.CHIRON, flags)[0]
                planets["Хирон"], speeds["Хирон"] = round(pos[0], 3), round(pos[3], 4)
            except swe.Error:
                pass
        if not exact or birth.place is None:
            return Chart(planets, exact_time=False, speeds=speeds)
        cusps, ascmc = swe.houses_ex(jd, birth.place.lat, birth.place.lon, b"P")
        planets["Асцендент"], planets["MC"] = round(ascmc[0], 3), round(ascmc[1], 3)
        return Chart(
            planets, exact_time=True, houses=[round(c, 3) for c in cusps], asc=round(ascmc[0], 3), mc=round(ascmc[1], 3), speeds=speeds
        )


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
