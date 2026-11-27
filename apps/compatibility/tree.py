"""«Наше дерево» on «Вдвоём»: a picture of what the two of you have done together, instead of bare numbers. It is
watered by what you do as a pair — a day you both answered the question is a leaf, a date of the week you both marked
is a blossom, a dream that came true is a lantern on a branch. It never wilts: a quiet day only means it waits.
It keeps changing after it is big: it lives through the seasons of the calendar and the time of day — a morning sun, an
evening one, a moon and stars at night, when the lanterns of your dreams glow — winter days are snowy or clear and
frosty, and past «Большое дерево» new things appear on it: fruit, a nest, a swing, a bench for your year.
"""

import hashlib
import math
from datetime import date

STAGES = ("Семечко", "Росток", "Саженец", "Молодое дерево", "Большое дерево")
# the kind of tree comes from the pair's dynamic (domain/archetypes.py) — compatibility shapes how it looks, never how
# big it is: a «friction» pair grows an oak, sturdy because it was tested. crown, blossom, accent colours
SPECIES = {  # name, crown, blossom (apples, acorns…), leaves
    "resonance": ("Сакура", "var(--color-a-soft)", "var(--color-paper)", "var(--color-a)"),
    "complement": ("Яблоня", "var(--color-sage)", "var(--color-risk)", "var(--color-synergy)"),
    "contrast": ("Клён", "var(--color-attention)", "var(--color-pair)", "var(--color-risk)"),
    "friction": ("Дуб", "var(--color-sage)", "var(--color-pair)", "var(--color-synergy-ink)"),
}
FRUIT = {"Сакура": ("вишни", "var(--color-risk-ink)"), "Яблоня": ("яблоки", "var(--color-risk)"),
         "Клён": ("крылатки", "var(--color-attention-ink)"), "Дуб": ("жёлуди", "var(--color-a-ink)")}  # fmt: skip
AUTUMN = {"Сакура": "var(--color-a)", "Яблоня": "var(--color-pair)", "Клён": "var(--color-risk)", "Дуб": "var(--color-attention)"}
SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
           6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}  # fmt: skip
SEASON_NAMES = {"spring": "весна", "summer": "лето", "autumn": "осень", "winter": "зима"}
SNOWY_DAYS = 60  # % of winter days when it snows (no sun then); the rest are clear and frosty
STARS = ((22, 18, 0), (58, 44, 1), (96, 14, 2), (128, 38, 3), (190, 16, 4), (222, 42, 1), (300, 70, 2), (12, 74, 3))  # x, y, twinkle
BULBS = ("var(--color-risk)", "var(--color-pair)", "var(--color-b)", "var(--color-synergy)")  # garland lights, in turn
FIREFLIES = ((44, 196, 0), (82, 182, 1), (232, 188, 2), (272, 200, 3), (120, 200, 4), (300, 184, 5))  # summer nights, over the grass
# what appears on a big tree, and when: (points, key, what the pair is told, the progress line before it, its name ahead)
MARKS = (
    (60, "big", "Выросло большое дерево", "", ""),
    (100, "fruit", "Созрели {fruit}", "до плодов", "{fruit}"),
    (150, "nest", "Птица свила гнездо", "до гнезда", "гнездо с птицей"),
    (200, "swing", "Появились качели", "до качелей", "качели"),
    (365, "bench", "Скамейка «наш год»", "до скамейки", "скамейка «наш год»"),
)
FRUIT_AT = ((118, 140), (140, 156), (176, 160), (204, 146), (222, 124), (98, 118))  # on the big crown's lower half
# where the path's marks go on the visible part of each trunk: the ribbon of «Глубже», the heart of «Откровенно»
TRUNK = {2: (161, 172, 156, 10, 190), 3: (160, 176, 152, 16, 195), 4: (158, 184, 147, 22, 198)}  # x, ribbon y, its left, width, heart y
# the season in motion: leaves or petals coming down from the crown and lying on the grass, snow over the whole sky
FALLING = ((124, 150, 0), (150, 162, 1), (186, 148, 2), (206, 160, 3), (138, 134, 4))  # x, y, which one (its delay)
FALLEN = ((118, 214, 20), (134, 220, -30), (178, 222, 10), (196, 215, -15), (214, 221, 35))  # x, y, angle
SNOWFALL = tuple((20 + 32 * k, (-4, 20, -10, 30, 6)[k % 5], k) for k in range(10))  # across the sky, at different heights
HEAD_START_MONTHS = 18  # a month together is a point of head start, up to a year and a half
AT = (0, 1, 5, 20, 60)  # growth points where each stage begins
CROWN = {2: (160, 112, 42), 3: (160, 98, 64), 4: (160, 88, 84)}  # crown centre and radius per stage, 320 × 220 scene
LEAVES, BLOSSOMS, LANTERNS = 24, 10, 8  # how many of each the crown can show


def points(answers: int, dates: int, dreams: int) -> int:
    return answers + 3 * dates + 5 * dreams


def _spots(stage: int, n: int) -> list[tuple[int, int]]:
    """n spots spread evenly over the crown (a sunflower spiral), the same every time."""
    cx, cy, r = CROWN[stage]
    out = []
    for i in range(n):
        k, a = math.sqrt((i + 0.5) / n), i * 2.39996
        out.append((round(cx + r * 0.86 * k * math.cos(a)), round(cy + r * 0.7 * k * math.sin(a))))
    return out


def _cap(x: int, y: int, r: int, at: float, half: float) -> str:
    """Snow lying on a round of the crown: an arc along its edge, centred `at` degrees from the top (minus is left),
    `half` degrees each way, with a scalloped lower edge — an SVG path."""
    pt = [(x + r * math.sin(math.radians(a)), y - r * math.cos(math.radians(a))) for a in (at - half, at + half)]
    (lx, ly), (rx, ry) = pt
    nx, ny = x - (lx + rx) / 2, y - (ly + ry) / 2  # towards the centre: the scallops dip that way
    k = 0.1 * r / math.hypot(nx, ny)
    d = f"M{lx:.1f} {ly:.1f}A{r} {r} 0 0 1 {rx:.1f} {ry:.1f}"
    for i in range(3):  # back along the chord in three dips
        (ax, ay), (bx, by) = [(rx + (lx - rx) * t / 3, ry + (ly - ry) * t / 3) for t in (i, i + 1)]
        d += f"Q{(ax + bx) / 2 + nx * k * 2:.1f} {(ay + by) / 2 + ny * k * 2:.1f} {bx:.1f} {by:.1f}"
    return d + "z"


def holiday(day: date) -> str:
    """The New Year holidays, 20 December to 10 January, named by their December so the toast says it once a winter."""
    if day.month == 12 and day.day >= 20:
        return f"newyear-{day.year}"
    return f"newyear-{day.year - 1}" if day.month == 1 and day.day <= 10 else ""


def _garland(stage: int) -> dict:
    """A string of lights for the holidays: three swags across the crown, each dipping twice, a bulb every few steps —
    or, while the tree is still a seed or a sprout, one swag on the grass round it. {"wires": [path], "bulbs": [(x, y,
    colour, twinkle)]}."""
    rows = []
    if stage >= 2:
        cx, cy, r = CROWN[stage]
        for dy, tilt in ((-0.5, -1), (-0.05, 1), (0.4, -1)):  # tilted in turn, as if wound round the crown
            y, w = cy + dy * r, math.sqrt(r * r - (dy * r) ** 2) * 0.86
            rows.append(((cx - w, y - tilt * 0.06 * r), (cx + w, y + tilt * 0.06 * r), 0.28 * r))
    else:
        rows.append(((128.0, 212.0), (192.0, 212.0), 16.0))
    wires, bulbs = [], []
    for a, b, sag in rows:
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d = f"M{a[0]:.1f} {a[1]:.1f}"
        for p0, p1 in ((a, mid), (mid, b)):
            c = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 + sag)
            d += f"Q{c[0]:.1f} {c[1]:.1f} {p1[0]:.1f} {p1[1]:.1f}"
            for t in (0.15, 0.5, 0.85):
                x, y = ((1 - t) ** 2 * p0[k] + 2 * t * (1 - t) * c[k] + t * t * p1[k] for k in (0, 1))
                bulbs.append((round(x), round(y), BULBS[len(bulbs) % len(BULBS)], len(bulbs) % 5))
        wires.append(d)
    return {"wires": wires, "bulbs": bulbs}


def season(month: int) -> str:
    return SEASONS[month]


def daytime(hour: int) -> str:
    """Part of the day for the sky: the device's clock decides on the page, this is the first guess from the server's."""
    return "morning" if 5 <= hour < 11 else "day" if 11 <= hour < 17 else "evening" if 17 <= hour < 21 else "night"


def snowing(day: date) -> bool:
    """Whether it snows on the tree that day — the same for both of you, different from day to day."""
    return int(hashlib.sha256(day.isoformat().encode()).hexdigest(), 16) % 100 < SNOWY_DAYS


def grow(answers: int, dates: int, dreams: int, watered_today: bool, months: int = 0, kind: str = "complement",
         season: str = "summer", snow: bool = False, hour: int = 12, holiday: str = "") -> dict:  # fmt: skip
    """Stage, progress to whatever comes next (a stage, then the marks of a big tree), and where leaves, blossoms and
    lanterns go. months together give a head start, so a couple of three years doesn't begin from a seed; kind picks
    the species; season dresses it — blossom in spring, colour in autumn, snow in winter, falling on snowy days (`snow`);
    hour sets the sky until the device's clock takes over; on a holiday (holiday()) it wears a garland."""
    head = min(max(months, 0), HEAD_START_MONTHS)
    p = points(answers, dates, dreams) + head
    stage = max(i for i, at in enumerate(AT) if p >= at)
    steps = sorted(set(AT) | {at for at, *_ in MARKS})  # every point where something new appears
    nxt = next((at for at in steps if at > p), None)
    prev = max(at for at in steps if at <= p)
    species, crown, blossom, leaf = SPECIES.get(kind, SPECIES["complement"])
    fruit, fruit_fill = FRUIT[species]
    tree = {"stage": stage, "name": STAGES[stage], "points": p, "head": head, "next_at": nxt, "watered": watered_today}
    tree |= {"species": species, "crown_fill": AUTUMN[species] if season == "autumn" else crown, "blossom_fill": blossom,
             "leaf_fill": leaf, "fruit_fill": fruit_fill, "season": season, "season_name": SEASON_NAMES[season]}  # fmt: skip
    tree |= {"crown": [], "leaves": [], "blossoms": [], "lanterns": [], "petals": [], "snow": []}
    tree["trunk"] = dict(zip(("x", "ribbon", "left", "width", "heart"), TRUNK[stage], strict=True)) if stage in TRUNK else None
    tree["progress"] = 100 if nxt is None else round(100 * (p - prev) / (nxt - prev))
    tree["next_label"] = next((before for at, _, _, before, _ in MARKS if at == nxt and before), "до следующего роста")
    tree["marks"] = [(key, title.format(fruit=fruit)) for at, key, title, *_ in MARKS if p >= at]
    tree["has"] = {key for key, _ in tree["marks"]}
    tree["ahead"] = [name.format(fruit=fruit) for at, *_, name in MARKS if p < at and name]
    tree["fruit"] = list(FRUIT_AT) if "fruit" in tree["has"] else []
    tree |= {"falling": FALLING, "fallen": FALLEN, "snowfall": SNOWFALL, "stars": STARS, "fireflies": FIREFLIES}
    tree |= {"snowing": snow and season == "winter", "time": daytime(hour), "holiday": holiday}
    tree["garland"] = _garland(stage) if holiday else None
    tree["last_mark"] = tree["marks"][-1][1] if tree["marks"] else ""
    tree["petal_fill"] = "var(--color-paper)" if species == "Сакура" else "var(--color-a-soft)"  # a pink tree blooms white
    if stage >= 2:
        cx, cy, r = CROWN[stage]  # the crown: one big round and three around it, like a child would draw it
        around = ((-0.62, 0.22, 0.68), (0.62, 0.18, 0.7), (-0.1, -0.5, 0.66))
        tree["crown"] = [(cx + round(r * dx), cy + round(r * dy), round(r * k)) for dx, dy, k in around] + [(cx, cy, r)]
        spots = _spots(stage, LEAVES + BLOSSOMS + LANTERNS)
        tree["lanterns"] = spots[1::5][: min(dreams, LANTERNS)]
        tree["blossoms"] = spots[3::5][: min(dates, BLOSSOMS)]
        taken = set(spots[1::5]) | set(spots[3::5])
        tree["leaves"] = [s for s in spots if s not in taken][: min(answers, LEAVES)]
        if season == "spring":  # in bloom: petals over the whole crown, on top of whatever you grew
            tree["petals"] = _spots(stage, 13)
        if season == "winter":  # snow along the upper edge of the crown: the outer shoulders, the top, the main round
            tree["snow"] = [
                _cap(x, y, r, at, half)
                for (x, y, r), (at, half) in zip(tree["crown"], ((-52, 26), (52, 26), (-6, 40), (0, 38)), strict=True)
            ]
    return tree


if __name__ == "__main__":
    assert grow(0, 0, 0, False)["name"] == "Семечко" and grow(1, 0, 0, True)["stage"] == 1
    t = grow(12, 2, 1, True)  # 12 + 6 + 5 = 23 points
    assert t["stage"] == 3 and t["next_at"] == 60 and t["progress"] == 8
    assert len(t["crown"]) == 4 and len(t["leaves"]) == 12 and len(t["blossoms"]) == 2 and len(t["lanterns"]) == 1
    assert not set(t["leaves"]) & set(t["blossoms"]) and not set(t["leaves"]) & set(t["lanterns"])  # nothing on top of each other
    old = grow(0, 0, 0, False, months=36)  # three years together: a head start, not a seed
    assert old["head"] == 18 and old["name"] == "Саженец"
    assert grow(0, 0, 0, False, kind="friction")["species"] == "Дуб" and grow(0, 0, 0, False, kind="?")["species"] == "Яблоня"
    big = grow(300, 40, 20, False)
    assert big["name"] == "Большое дерево" and big["progress"] == 100 and len(big["leaves"]) <= LEAVES and len(big["lanterns"]) == LANTERNS
    cx, cy, r = CROWN[4]
    assert all(abs(x - cx) <= r and abs(y - cy) <= r for x, y in big["leaves"] + big["fruit"])  # all on the crown
    assert big["has"] == {"big", "fruit", "nest", "swing", "bench"} and big["next_at"] is None and big["ahead"] == []
    assert grow(120, 0, 0, False)["ahead"] == ["гнездо с птицей", "качели", "скамейка «наш год»"]
    one = grow(60, 0, 0, False)  # just big: the bar keeps going, now towards the fruit
    assert one["has"] == {"big"} and one["next_at"] == 100 and one["next_label"] == "до плодов" and one["progress"] == 0
    assert grow(120, 0, 0, False, kind="friction")["marks"][-1] == ("fruit", "Созрели жёлуди")
    assert grow(23, 0, 0, False)["next_label"] == "до следующего роста"
    assert holiday(date(2026, 12, 20)) == holiday(date(2027, 1, 10)) == "newyear-2026" and holiday(date(2026, 12, 19)) == ""
    assert holiday(date(2027, 1, 11)) == "" and grow(30, 0, 0, False)["garland"] is None
    for n in (0, 1, 20, 300):  # every bulb on the crown, or on the grass while there is no crown yet
        g = grow(n, 0, 0, False, holiday="newyear-2026")["garland"]
        cx, cy, r = CROWN.get(grow(n, 0, 0, False)["stage"], (160, 212, 40))
        assert g["bulbs"] and all(math.hypot(x - cx, y - cy) <= r for x, y, *_ in g["bulbs"]), n
        assert all(isinstance(x, int) and isinstance(y, int) for x, y, *_ in g["bulbs"])  # «119,5» in a Russian template
    assert daytime(6) == "morning" and daytime(12) == "day" and daytime(19) == "evening" and daytime(23) == daytime(2) == "night"
    snowy = sum(snowing(date.fromordinal(date(2026, 12, 1).toordinal() + n)) for n in range(90))
    assert 35 < snowy < 70 and snowing(date(2027, 1, 5)) == snowing(date(2027, 1, 5))  # most winter days, the same for both
    assert not grow(30, 0, 0, False, snow=True)["snowing"] and grow(30, 0, 0, False, season="winter", snow=True)["snowing"]
    assert season(11) == "autumn" and season(1) == "winter" and season(4) == "spring" and season(7) == "summer"
    fall = grow(30, 0, 0, False, kind="contrast", season="autumn")
    assert fall["crown_fill"] == AUTUMN["Клён"] and fall["season_name"] == "осень" and not fall["snow"] and not fall["petals"]
    assert (
        len(grow(30, 0, 0, False, season="winter")["snow"]) == 4
        and _cap(160, 100, 50, 0, 40).startswith("M127.9 61.7A50")
        and grow(30, 0, 0, False, season="spring")["petals"]
    )
    assert grow(0, 0, 0, False, season="winter")["snow"] == [] and grow(0, 0, 0, False)["trunk"] is None  # a seed has no crown
    print("ok")
