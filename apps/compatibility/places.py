"""Birthplaces anywhere on Earth: search by name (Russian or Latin, any spelling), the nearest place to a map
point, and the places inside a map view. Data: GeoNames cities500 in our own database, nothing leaves the server.
"""

import math
import re
import unicodedata
from zoneinfo import available_timezones

from django.db.models import Q

from .models import GeoPlace

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "i",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ї": "i", "є": "e", "ґ": "g",
}  # fmt: skip
# Spellings that differ between transliterations collapse to one form: Сингараджа = Singaraja, Таллин = Tallinn.
_LATIN = [("shch", "sh"), ("dzh", "j"), ("dj", "j"), ("zh", "j"), ("kh", "h"), ("tz", "c"), ("ts", "c"), ("ck", "k"),
          ("ph", "f"), ("w", "v"), ("q", "k"), ("x", "ks"), ("y", "i")]  # fmt: skip


def search_key(text: str) -> str:
    """One spelling-independent key for a place name, used for prefix search."""
    s = text.lower().replace("дж", "j")
    s = "".join(_CYR.get(c, c) for c in s)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    for a, b in _LATIN:
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]", "", s)
    s = re.sub(r"^ie", "e", s)  # Екатеринбург = Yekaterinburg
    return re.sub(r"(.)\1+", r"\1", s)


def as_dict(p: GeoPlace) -> dict:
    return {
        "id": p.id, "name": p.name, "name_en": p.name_en, "country": p.country,
        "lat": p.lat, "lon": p.lon, "tz": p.tz, "pop": p.population,
    }  # fmt: skip


def search(q: str, limit: int = 8) -> list[GeoPlace]:
    key = search_key(q)
    if len(key) < 2:
        return []
    return list(GeoPlace.objects.filter(Q(key__startswith=key) | Q(key_en__startswith=key)).order_by("-population")[:limit])


def resolve(text: str) -> GeoPlace | None:
    """A typed name without a map point: the most populous place with exactly that name."""
    key = search_key(text.split(",")[0])
    if not key:
        return None
    return GeoPlace.objects.filter(Q(key=key) | Q(key_en=key)).order_by("-population").first()


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def nearest(lat: float, lon: float) -> tuple[GeoPlace, float] | None:
    """Nearest known place and the distance to it: it names a map point and lends it its time zone."""
    for r in (0.3, 1, 3, 10, 30):
        found = list(GeoPlace.objects.filter(lat__range=(lat - r, lat + r), lon__range=(lon - r * 2, lon + r * 2)))
        if found:
            best = min(found, key=lambda p: km(lat, lon, p.lat, p.lon))
            return best, km(lat, lon, best.lat, best.lon)
    return None


def in_box(w: float, s: float, e: float, n: float, limit: int = 160) -> list[GeoPlace]:
    qs = GeoPlace.objects.filter(lat__range=(s, n))
    qs = qs.filter(lon__range=(w, e)) if w <= e else qs.exclude(lon__range=(e, w))  # a view across the 180th meridian
    return list(qs.order_by("-population")[:limit])


_ZONES: set[str] = set()


def coords(lat: str | None, lon: str | None, tz: str | None) -> tuple[float, float, str] | None:
    """A map point from a form (trust boundary): numbers in range and a real IANA time zone, else None."""
    if not _ZONES:
        _ZONES.update(available_timezones())
    try:
        la, lo = float(lat or ""), float(lon or "")
    except ValueError:
        return None
    if not (math.isfinite(la) and math.isfinite(lo) and -90 <= la <= 90 and -180 <= lo <= 180 and tz in _ZONES):
        return None
    return round(la, 5), round(lo, 5), str(tz)
