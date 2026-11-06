"""Natal charts, synastry, house overlays and the composite chart. Pure domain — an EphemerisProvider fills Chart.

Methodology: docs/methodology/astrology.md.
"""

import datetime as dt
from dataclasses import dataclass, field
from itertools import combinations
from typing import Literal

from apps.core.domain.names import gen
from apps.core.domain.scoring import Factor, ScoreResult, clamp

SIGNS = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева", "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"]
SIGN_GLYPH = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
SIGN_ELEMENT = ["fire", "earth", "air", "water"] * 3
SIGN_MODALITY = ["cardinal", "fixed", "mutable"] * 4
ELEMENT_RU = {"fire": "огонь", "earth": "земля", "air": "воздух", "water": "вода"}
MODALITY_RU = {"cardinal": "кардинальный", "fixed": "фиксированный", "mutable": "мутабельный"}


@dataclass(frozen=True)
class Point:
    name: str
    glyph: str
    kind: str  # luminary | personal | social | outer | point | angle
    orb: float
    weight: float  # importance in a relationship


_POINTS = [
    Point("Солнце", "☉", "luminary", 8, 1.0),
    Point("Луна", "☽", "luminary", 8, 1.0),
    Point("Меркурий", "☿", "personal", 6, 0.7),
    Point("Венера", "♀", "personal", 6, 1.0),
    Point("Марс", "♂", "personal", 6, 1.0),
    Point("Юпитер", "♃", "social", 5, 0.6),
    Point("Сатурн", "♄", "social", 5, 0.8),
    Point("Уран", "♅", "outer", 4, 0.5),
    Point("Нептун", "♆", "outer", 4, 0.5),
    Point("Плутон", "♇", "outer", 4, 0.7),
    Point("Северный узел", "☊", "point", 3, 0.5),
    Point("Лилит", "⚸", "point", 3, 0.5),
    Point("Хирон", "⚷", "point", 3, 0.5),
    Point("Асцендент", "ASC", "angle", 5, 0.9),
    Point("MC", "MC", "angle", 4, 0.6),
]
POINTS = {p.name: p for p in _POINTS}
PLANETS = ["Солнце", "Луна", "Меркурий", "Венера", "Марс", "Юпитер", "Сатурн"]  # classical seven
BODIES = PLANETS + ["Уран", "Нептун", "Плутон", "Северный узел", "Лилит", "Хирон"]
ANGLES = ["Асцендент", "MC"]
OUTER = {"Уран", "Нептун", "Плутон"}
NO_RETRO = {"Солнце", "Луна", "Северный узел", "Лилит", "Асцендент", "MC"}

DOMICILE = {
    "Солнце": ["Лев"],
    "Луна": ["Рак"],
    "Меркурий": ["Близнецы", "Дева"],
    "Венера": ["Телец", "Весы"],
    "Марс": ["Овен", "Скорпион"],
    "Юпитер": ["Стрелец", "Рыбы"],
    "Сатурн": ["Козерог", "Водолей"],
    "Уран": ["Водолей"],
    "Нептун": ["Рыбы"],
    "Плутон": ["Скорпион"],
}
EXALTATION = {"Солнце": "Овен", "Луна": "Телец", "Меркурий": "Дева", "Венера": "Рыбы", "Марс": "Козерог", "Юпитер": "Рак", "Сатурн": "Весы"}
HOUSE_AREA = {
    1: "внешность и первое впечатление",
    2: "деньги и ценности",
    3: "общение и повседневные разговоры",
    4: "дом и корни",
    5: "романтика, радость, дети",
    6: "будни и забота",
    7: "партнёрство",
    8: "близость, секс, общие ресурсы",
    9: "мировоззрение и путешествия",
    10: "статус и цели",
    11: "друзья и мечты",
    12: "тайное и бессознательное",
}


def _opposite(sign: str) -> str:
    return SIGNS[(SIGNS.index(sign) + 6) % 12]


def sign_of(lon: float) -> str:
    return SIGNS[int(lon // 30) % 12]


def degree_label(lon: float) -> str:
    d = lon % 30
    minutes = round((d - int(d)) * 60)
    return f"{int(d) + minutes // 60}°{minutes % 60:02d}′"


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float
    tz: str


@dataclass(frozen=True)
class BirthData:
    day: dt.date
    time: dt.time | None = None
    place: Place | None = None


@dataclass(frozen=True)
class Chart:
    planets: dict[str, float]  # ecliptic longitude of every computed point (angles only with exact time)
    exact_time: bool
    houses: list[float] | None = None  # 12 Placidus cusps
    asc: float | None = None
    mc: float | None = None
    speeds: dict[str, float] = field(default_factory=dict)

    def sign(self, point: str) -> str:
        return sign_of(self.planets[point])

    def degree(self, point: str) -> str:
        return degree_label(self.planets[point])

    def retro(self, point: str) -> bool:
        return point not in NO_RETRO and self.speeds.get(point, 0) < 0

    def house_of(self, lon: float) -> int | None:
        if not self.houses:
            return None
        for i in range(12):
            start, end = self.houses[i], self.houses[(i + 1) % 12]
            if (lon - start) % 360 < (end - start) % 360:
                return i + 1
        return None

    def house(self, point: str) -> int | None:
        return self.house_of(self.planets[point])

    def dignity(self, point: str) -> str | None:
        sign = self.sign(point)
        if sign in DOMICILE.get(point, []):
            return "обитель"
        if EXALTATION.get(point) == sign:
            return "экзальтация"
        if sign in [_opposite(s) for s in DOMICILE.get(point, [])]:
            return "изгнание"
        if point in EXALTATION and _opposite(EXALTATION[point]) == sign:
            return "падение"
        return None

    @property
    def points(self) -> list[str]:
        return [p for p in BODIES + ANGLES if p in self.planets]


@dataclass(frozen=True)
class AspectKind:
    key: str
    name: str
    symbol: str
    angle: int
    strength: float
    major: bool = True


ASPECTS = [
    AspectKind("conj", "соединение", "☌", 0, 9),
    AspectKind("sextile", "секстиль", "⚹", 60, 7),
    AspectKind("square", "квадрат", "□", 90, 9),
    AspectKind("trine", "трин", "△", 120, 10),
    AspectKind("opp", "оппозиция", "☍", 180, 7),
    AspectKind("semisextile", "полусекстиль", "⚺", 30, 2, False),
    AspectKind("semisquare", "полуквадрат", "∠", 45, 3, False),
    AspectKind("sesquiquadrate", "полутораквадрат", "⚼", 135, 3, False),
    AspectKind("quincunx", "квинконс", "⚻", 150, 4, False),
]
MINOR_ORB = 2.0
BENEFIC, HARD = {"Венера", "Юпитер"}, {"Марс", "Сатурн", "Плутон"}
ATTRACTION_OPP = [{"Венера", "Марс"}, {"Солнце", "Луна"}, {"Венера", "Плутон"}, {"Солнце", "Венера"}]


def _pairs(*groups: tuple[str, ...]) -> list[frozenset[str]]:
    return [frozenset(g) for g in groups]


# Life spheres an aspect between two points speaks about (symmetric; a one-element tuple means «with itself»).
SPHERE_PAIRS: dict[str, list[frozenset[str]]] = {
    "attraction": _pairs(
        ("Венера", "Марс"),
        ("Солнце", "Луна"),
        ("Солнце", "Венера"),
        ("Венера", "Асцендент"),
        ("Венера",),
        ("Луна", "Асцендент"),
        ("Солнце", "Асцендент"),
    ),
    "sex": _pairs(
        ("Венера", "Марс"),
        ("Марс",),
        ("Марс", "Плутон"),
        ("Венера", "Плутон"),
        ("Марс", "Лилит"),
        ("Венера", "Лилит"),
        ("Солнце", "Марс"),
        ("Марс", "Асцендент"),
        ("Луна", "Марс"),
    ),
    "emotions": _pairs(("Луна",), ("Луна", "Венера"), ("Солнце", "Луна"), ("Луна", "Нептун"), ("Луна", "Сатурн"), ("Луна", "Юпитер")),
    "talk": _pairs(
        ("Меркурий",),
        ("Меркурий", "Луна"),
        ("Меркурий", "Солнце"),
        ("Меркурий", "Венера"),
        ("Меркурий", "Марс"),
        ("Меркурий", "Сатурн"),
        ("Меркурий", "Юпитер"),
        ("Меркурий", "Уран"),
    ),
    "conflicts": _pairs(
        ("Марс", "Сатурн"), ("Марс", "Меркурий"), ("Марс", "Луна"), ("Марс",), ("Марс", "Уран"), ("Солнце", "Марс"), ("Марс", "Плутон")
    ),
    "trust": _pairs(
        ("Венера", "Плутон"),
        ("Луна", "Плутон"),
        ("Венера", "Сатурн"),
        ("Венера", "Нептун"),
        ("Луна", "Нептун"),
        ("Венера", "Уран"),
        ("Луна", "Уран"),
    ),
    "power": _pairs(
        ("Солнце", "Плутон"), ("Марс", "Плутон"), ("Солнце", "Сатурн"), ("Марс", "Сатурн"), ("Меркурий", "Плутон"), ("Солнце",)
    ),
    "shadows": _pairs(
        ("Луна", "Плутон"),
        ("Венера", "Плутон"),
        ("Солнце", "Плутон"),
        ("Луна", "Лилит"),
        ("Венера", "Лилит"),
        ("Луна", "Хирон"),
        ("Венера", "Хирон"),
        ("Солнце", "Хирон"),
        ("Луна", "Сатурн"),
        ("Солнце", "Нептун"),
        ("Северный узел", "Луна"),
        ("Северный узел", "Солнце"),
        ("Северный узел", "Венера"),
    ),
    "home": _pairs(("Луна", "Сатурн"), ("Луна", "Юпитер"), ("Венера", "Сатурн"), ("Луна", "Венера"), ("Луна",)),
    "money": _pairs(("Венера", "Юпитер"), ("Венера", "Сатурн"), ("Юпитер", "Сатурн"), ("Юпитер",)),
    "plans": _pairs(
        ("Солнце",), ("Солнце", "Юпитер"), ("Солнце", "Сатурн"), ("Северный узел", "Солнце"), ("MC", "Солнце"), ("Сатурн", "Юпитер")
    ),
    "people": _pairs(("Юпитер", "Луна"), ("Юпитер", "Меркурий"), ("Юпитер", "Солнце"), ("Венера", "Юпитер")),
    "growth": _pairs(
        ("Юпитер", "Солнце"),
        ("Северный узел", "Солнце"),
        ("Северный узел", "Луна"),
        ("Уран", "Солнце"),
        ("Юпитер", "Луна"),
        ("Северный узел", "Венера"),
    ),
}
HOUSE_SPHERES = {
    1: ["attraction"],
    2: ["money"],
    3: ["talk"],
    4: ["home", "emotions"],
    5: ["attraction", "sex"],
    6: ["home"],
    7: ["attraction", "plans"],
    8: ["sex", "trust", "shadows"],
    9: ["growth"],
    10: ["plans", "power"],
    11: ["people"],
    12: ["shadows"],
}
# the six scoring categories are fed by spheres
SPHERE_CATEGORY = {
    "attraction": "passion",
    "sex": "passion",
    "emotions": "emotions",
    "talk": "communication",
    "conflicts": "conflict",
    "power": "conflict",
    "trust": "emotions",
    "shadows": "conflict",
    "home": "home",
    "money": "values",
    "plans": "values",
    "people": "communication",
    "growth": "values",
}
CATEGORY_WEIGHT = {"passion": 0.2, "emotions": 0.2, "communication": 0.15, "values": 0.2, "conflict": 0.1, "home": 0.15}


def spheres_for(a: str, b: str) -> list[str]:
    key = frozenset((a, b))
    return [s for s, pairs in SPHERE_PAIRS.items() if key in pairs]


def category_for(spheres: list[str] | tuple[str, ...]) -> str | None:
    return SPHERE_CATEGORY[spheres[0]] if spheres else None


@dataclass(frozen=True)
class Hit:
    planet_a: str
    planet_b: str
    kind: AspectKind
    orb: float
    effect: float
    approximate: bool = False
    double: bool = False  # the same pair is aspected in both directions — a «double whammy»
    spheres: tuple[str, ...] = ()

    @property
    def tone(self) -> str:
        return "synergy" if self.effect >= 2 else "attention" if self.effect <= -2 else "neutral"

    @property
    def key(self) -> str:
        return f"{self.planet_a}:{self.kind.key}:{self.planet_b}"

    @property
    def meaning(self) -> str:  # one line; the full text comes from interpret.py or the knowledge base
        from .interpret import aspect_line

        return aspect_line(self)


def _effect(a: str, b: str, kind: AspectKind, tightness: float) -> float:
    s = kind.strength * tightness * (POINTS[a].weight + POINTS[b].weight) / 2
    pair = {a, b}
    if kind.key in {"trine", "sextile"}:
        return s
    if kind.key == "semisextile":
        return 0.3 * s
    if kind.key == "square":
        return -s
    if kind.key in {"semisquare", "sesquiquadrate"}:
        return -0.6 * s
    if kind.key == "quincunx":
        return -0.4 * s
    if kind.key == "conj":
        intense = pair & (HARD | {"Уран", "Нептун", "Лилит", "Хирон"})
        return -0.3 * s if intense and pair not in ({"Венера", "Марс"}, {"Венера", "Плутон"}, {"Марс", "Плутон"}) else s
    return 0.6 * s if pair in ATTRACTION_OPP else -0.5 * s  # opposition: attraction for classic pairs, tension otherwise


def synastry(a: Chart, b: Chart) -> list[Hit]:
    raw = []
    for pa in a.points:
        for pb in b.points:
            if (pa in OUTER and pb in OUTER) or (pa in ANGLES and pb in ANGLES):
                continue  # outer–outer contacts are generational: people born close together share them
            delta = abs((a.planets[pa] - b.planets[pb] + 180) % 360 - 180)
            limit = (POINTS[pa].orb + POINTS[pb].orb) / 2
            for kind in ASPECTS:
                lim = limit if kind.major else MINOR_ORB
                orb = abs(delta - kind.angle)
                if orb <= lim:
                    approx = "Луна" in (pa, pb) and not (a.exact_time and b.exact_time)
                    raw.append((pa, pb, kind, round(orb, 1), _effect(pa, pb, kind, 1 - 0.5 * orb / lim), approx))
    core = {"luminary", "personal"}
    seen = {(pa, pb) for pa, pb, kind, *_ in raw if kind.major}
    hits = []
    for pa, pb, kind, orb, eff, approx in raw:
        double = kind.major and pa != pb and (pb, pa) in seen and POINTS[pa].kind in core and POINTS[pb].kind in core
        hits.append(Hit(pa, pb, kind, orb, round(eff * (1.4 if double else 1), 2), approx, double, tuple(spheres_for(pa, pb))))
    return sorted(hits, key=lambda h: (not h.kind.major, -abs(h.effect), h.orb))


@dataclass(frozen=True)
class OverlayHit:
    planet: str
    owner: Literal["a", "b"]  # whose planet
    house: int  # in the other's chart
    effect: float
    spheres: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.planet}:{self.house}"


@dataclass
class HouseOverlay:
    hits: list[OverlayHit] = field(default_factory=list)
    lines: list[Factor] = field(default_factory=list)
    bonus: dict[str, float] = field(default_factory=dict)


def houses_overlay(a: Chart, b: Chart, name_a: str, name_b: str) -> HouseOverlay:
    ov = HouseOverlay()
    sides: list[tuple[Chart, Chart, Literal["a", "b"], str, str]] = [(a, b, "a", name_a, name_b), (b, a, "b", name_b, name_a)]
    for owner, other, side, who, whose in sides:
        if not other.houses:
            continue
        for planet in [p for p in BODIES if p in owner.planets]:
            house = other.house_of(owner.planets[planet])
            if not house:
                continue
            w = POINTS[planet].weight
            if planet in BENEFIC | {"Солнце", "Луна"} and house in (1, 4, 5, 7):
                effect = 3 * w
            elif planet in HARD and house in (1, 7, 8):
                effect = -2 * w
            else:
                effect = 0.5 * w
            spheres = tuple(HOUSE_SPHERES[house])
            ov.hits.append(OverlayHit(planet, side, house, round(effect, 2), spheres))
            if POINTS[planet].kind in ("luminary", "personal") or planet == "Плутон":
                cat = SPHERE_CATEGORY[spheres[0]]
                ov.bonus[cat] = ov.bonus.get(cat, 0) + effect
                ov.lines.append(
                    Factor(
                        f"{planet} ({who}) в {house}-м доме {gen(whose)}",
                        f"дом {house}: {HOUSE_AREA[house]}",
                        round(effect / 10, 2),
                        "symbolic",
                        cat,
                    )
                )
    return ov


@dataclass(frozen=True)
class Composite:
    planets: dict[str, float]
    houses: list[float] | None
    aspects: list[tuple[str, str, AspectKind, float]]

    def sign(self, p: str) -> str:
        return sign_of(self.planets[p])

    def house(self, p: str) -> int | None:
        return Chart(self.planets, bool(self.houses), self.houses).house(p)


def _midpoint(x: float, y: float) -> float:
    d = (y - x + 360) % 360
    return (x + d / 2) % 360 if d <= 180 else (y + (360 - d) / 2) % 360


def composite(a: Chart, b: Chart) -> Composite:
    """Midpoint composite: the relationship as a chart of its own."""
    planets = {p: round(_midpoint(a.planets[p], b.planets[p]), 3) for p in a.points if p in b.planets}
    houses = [round(_midpoint(x, y), 3) for x, y in zip(a.houses, b.houses, strict=True)] if a.houses and b.houses else None
    aspects = []
    for p, q in combinations([x for x in BODIES if x in planets], 2):
        if p in OUTER and q in OUTER:
            continue
        delta = abs((planets[p] - planets[q] + 180) % 360 - 180)
        for kind in [k for k in ASPECTS if k.major]:
            orb = abs(delta - kind.angle)
            if orb <= (POINTS[p].orb + POINTS[q].orb) / 2 - 1:
                aspects.append((p, q, kind, round(orb, 1)))
    return Composite(planets, houses, sorted(aspects, key=lambda x: x[3]))


@dataclass(frozen=True)
class Balance:
    elements: dict[str, int]
    modalities: dict[str, int]


def balance(c: Chart) -> Balance:
    """Sun, Moon and Ascendant count double; the other classical planets once."""
    weights = {p: 2.0 if p in ("Солнце", "Луна", "Асцендент") else 1.0 for p in [*PLANETS, "Асцендент"] if p in c.planets}
    el = dict.fromkeys(ELEMENT_RU, 0.0)
    mo = dict.fromkeys(MODALITY_RU, 0.0)
    for p, w in weights.items():
        idx = int(c.planets[p] // 30) % 12
        el[SIGN_ELEMENT[idx]] += w
        mo[SIGN_MODALITY[idx]] += w
    total = sum(weights.values())
    return Balance({k: round(v / total * 100) for k, v in el.items()}, {k: round(v / total * 100) for k, v in mo.items()})


def element_counts(c: Chart) -> dict[str, int]:
    counts = dict.fromkeys(ELEMENT_RU, 0)
    for planet in ("Солнце", "Луна", "Меркурий", "Венера", "Марс"):
        counts[SIGN_ELEMENT[int(c.planets[planet] // 30) % 12]] += 1
    return counts


def dominant_element(c: Chart) -> str:
    counts = element_counts(c)
    sun = SIGN_ELEMENT[int(c.planets["Солнце"] // 30) % 12]
    return max(counts, key=lambda e: (counts[e], e == sun))


def sphere_effects(hits: list[Hit], overlay: HouseOverlay | None = None) -> dict[str, list[float]]:
    """Signed contributions per life sphere (minor aspects count half)."""
    out: dict[str, list[float]] = {s: [] for s in SPHERE_PAIRS}
    for h in hits:
        for s in h.spheres:
            out[s].append(h.effect * (1.0 if h.kind.major else 0.5))
    for o in overlay.hits if overlay else []:
        for s in o.spheres:
            out[s].append(o.effect)
    return out


def sphere_score(effects: list[float]) -> int | None:
    """Mean contribution, not the sum — a pair with many contacts is not automatically «more compatible»."""
    return clamp(62 + 5.0 * sum(effects) / len(effects), 25, 94) if effects else None


def score(a: Chart, b: Chart, hits: list[Hit], overlay: HouseOverlay | None = None) -> ScoreResult:
    per_cat: dict[str, list[float]] = {c: [] for c in CATEGORY_WEIGHT}
    for sphere, effects in sphere_effects(hits, overlay).items():
        per_cat[SPHERE_CATEGORY[sphere]] += effects
    cats = {c: float(sphere_score(v) or 62) for c, v in per_cat.items()}
    categories = {c: clamp(v, 25, 94) for c, v in cats.items()}
    total = sum(categories[c] * w for c, w in CATEGORY_WEIGHT.items())
    confidence = 92 if a.exact_time and b.exact_time else 72 if (a.exact_time or b.exact_time) else 58
    factors = [
        Factor(
            f"{h.planet_a} А {h.kind.symbol} {h.planet_b} Б",
            f"{h.kind.name}, орб {h.orb}°"
            + (" · двойной аспект" if h.double else "")
            + (" · Луна приблизительно" if h.approximate else ""),
            round(h.effect / 10, 2),
            "symbolic",
            category_for(h.spheres),
        )
        for h in hits
        if h.kind.major
    ][:16]
    factors += overlay.lines if overlay else []
    return ScoreResult(clamp(total), confidence, factors, categories)
