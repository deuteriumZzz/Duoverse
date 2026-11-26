"""«Наше дерево» on «Вдвоём»: a picture of what the two of you have done together, instead of bare numbers. It is
watered by what you do as a pair — a day you both answered the question is a leaf, a date of the week you both marked
is a blossom, a dream that came true is a lantern on a branch. It never wilts: a quiet day only means it waits.
"""

import math

STAGES = ("Семечко", "Росток", "Саженец", "Молодое дерево", "Большое дерево")
# the kind of tree comes from the pair's dynamic (domain/archetypes.py) — compatibility shapes how it looks, never how
# big it is: a «friction» pair grows an oak, sturdy because it was tested. crown, blossom, accent colours
SPECIES = {  # name, crown, blossom (apples, acorns…), leaves
    "resonance": ("Сакура", "var(--color-a-soft)", "var(--color-paper)", "var(--color-a)"),
    "complement": ("Яблоня", "var(--color-sage)", "var(--color-risk)", "var(--color-synergy)"),
    "contrast": ("Клён", "var(--color-attention)", "var(--color-pair)", "var(--color-risk)"),
    "friction": ("Дуб", "var(--color-sage)", "var(--color-pair)", "var(--color-synergy-ink)"),
}
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


def grow(answers: int, dates: int, dreams: int, watered_today: bool, months: int = 0, kind: str = "complement") -> dict:
    """Stage, progress to the next one, and where leaves, blossoms and lanterns go. months together give a head start,
    so a couple of three years doesn't begin from a seed; kind picks the species."""
    head = min(max(months, 0), HEAD_START_MONTHS)
    p = points(answers, dates, dreams) + head
    stage = max(i for i, at in enumerate(AT) if p >= at)
    nxt = AT[stage + 1] if stage + 1 < len(AT) else None
    species, crown, blossom, leaf = SPECIES.get(kind, SPECIES["complement"])
    tree = {"stage": stage, "name": STAGES[stage], "points": p, "head": head, "next_at": nxt, "watered": watered_today}
    tree |= {"species": species, "crown_fill": crown, "blossom_fill": blossom, "leaf_fill": leaf}
    tree |= {"crown": [], "leaves": [], "blossoms": [], "lanterns": []}
    tree["progress"] = 100 if nxt is None else round(100 * (p - AT[stage]) / (nxt - AT[stage]))
    if stage >= 2:
        cx, cy, r = CROWN[stage]  # the crown: one big round and three around it, like a child would draw it
        around = ((-0.62, 0.22, 0.68), (0.62, 0.18, 0.7), (-0.1, -0.5, 0.66))
        tree["crown"] = [(cx + round(r * dx), cy + round(r * dy), round(r * k)) for dx, dy, k in around] + [(cx, cy, r)]
        spots = _spots(stage, LEAVES + BLOSSOMS + LANTERNS)
        tree["lanterns"] = spots[1::5][: min(dreams, LANTERNS)]
        tree["blossoms"] = spots[3::5][: min(dates, BLOSSOMS)]
        taken = set(spots[1::5]) | set(spots[3::5])
        tree["leaves"] = [s for s in spots if s not in taken][: min(answers, LEAVES)]
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
    assert all(abs(x - cx) <= r and abs(y - cy) <= r for x, y in big["leaves"])  # all on the crown
    print("ok")
