"""Pythagorean numerology (ADR-0005). Pure functions; methodology in docs/methodology/numerology.md."""

from dataclasses import dataclass
from datetime import date

from apps.core.domain.scoring import Factor, ScoreResult, clamp

MASTER = {11, 22, 33}
_CYR = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
_LAT = "abcdefghijklmnopqrstuvwxyz"
LETTER_VALUE = {ch: i % 9 + 1 for alphabet in (_CYR, _LAT) for i, ch in enumerate(alphabet)}

KEYWORDS = {
    1: "лидерство и старт",
    2: "партнёрство и чуткость",
    3: "выражение и лёгкость",
    4: "порядок и надёжность",
    5: "свобода и перемены",
    6: "забота и дом",
    7: "анализ и глубина",
    8: "результат и ответственность",
    9: "широта и отдача",
    11: "интуиция и вдохновение",
    22: "большие замыслы",
    33: "служение и забота о других",
}
# temperament groups — numbers in one group share a rhythm
GROUP = {1: "drive", 5: "drive", 7: "drive", 2: "build", 4: "build", 8: "build", 3: "care", 6: "care", 9: "care"}
HARMONY = {frozenset(p) for p in [(1, 5), (2, 4), (2, 8), (3, 6), (3, 9), (4, 8), (6, 9), (1, 3), (2, 6), (5, 7)]}
TENSION = {frozenset(p) for p in [(1, 8), (4, 5), (3, 4), (7, 8), (1, 1), (5, 6)]}


def digits(n: int) -> int:
    return sum(int(c) for c in str(n))


def reduce(n: int, keep_master: bool = True) -> int:
    while n > 9 and not (keep_master and n in MASTER):
        n = digits(n)
    return n


def base(n: int) -> int:
    """Master numbers fold to their root for pairwise comparison: 11→2, 22→4, 33→6."""
    return reduce(n, keep_master=False)


@dataclass(frozen=True)
class Profile:
    life_path: int
    destiny: int | None
    personal_year: int
    matrix: dict[str, int]


def life_path(d: date) -> int:
    return reduce(digits(int(d.strftime("%d%m%Y"))))


def destiny(full_name: str) -> int | None:
    values = [LETTER_VALUE[ch] for ch in full_name.lower() if ch in LETTER_VALUE]
    return reduce(sum(values)) if values else None


def personal_year(d: date, today: date) -> int:
    return reduce(digits(d.day) + digits(d.month) + digits(today.year), keep_master=False)


def to22(n: int) -> int:
    while n > 22:
        n = digits(n) if n > 44 else n - 22
    return n or 22


def destiny_matrix(d: date) -> dict[str, int]:
    """Five key points from 22 arcana (our documented adaptation, symbolic layer)."""
    a, b, c = to22(d.day), to22(d.month), to22(digits(d.year))
    dd = to22(a + b + c)
    center = to22(a + b + c + dd)
    return {"Центр личности": center, "Отношения": to22(center + c), "Предназначение": to22(a + b), "Ресурс": c, "Зона роста": dd}


def profile(d: date, name: str | None, today: date) -> Profile:
    return Profile(life_path(d), destiny(name) if name else None, personal_year(d, today), destiny_matrix(d))


def pair_number(a: Profile, b: Profile) -> int:
    return reduce(base(a.life_path) + base(b.life_path), keep_master=False)


def relation(x: int, y: int) -> tuple[int, str]:
    """Score and wording for two numbers. Explicit tables, no hidden weights."""
    bx, by = base(x), base(y)
    if bx == by:
        return 78, "одно число — похожий ритм, но и похожие слепые зоны"
    if frozenset((bx, by)) in HARMONY:
        return 88, "гармоничная пара чисел — сильные стороны дополняют друг друга"
    if frozenset((bx, by)) in TENSION:
        return 52, "напряжённая пара — разные скорости и приоритеты"
    if GROUP[bx] == GROUP[by]:
        return 74, "одна группа — общий темп"
    return 64, "разные группы — нужно договариваться о ритме"


def score(a: Profile, b: Profile) -> ScoreResult:
    lp, lp_text = relation(a.life_path, b.life_path)
    parts = [(lp, 0.6, Factor(f"Число пути {a.life_path} + {b.life_path}", lp_text, (lp - 65) / 30, "symbolic"))]
    if a.destiny and b.destiny:
        ds, ds_text = relation(a.destiny, b.destiny)
        parts.append((ds, 0.25, Factor(f"Число судьбы {a.destiny} + {b.destiny}", ds_text, (ds - 65) / 30, "symbolic")))
    same_cycle = a.personal_year == b.personal_year or abs(a.personal_year - b.personal_year) == 1
    py = 76 if same_cycle else 60
    parts.append(
        (
            py,
            0.15,
            Factor(
                f"Личный год {a.personal_year} и {b.personal_year}",
                "близкие циклы — планы проще синхронизировать" if same_cycle else "разные циклы — сверяйте планы чаще",
                (py - 65) / 30,
                "symbolic",
            ),
        )
    )
    total = sum(s * w for s, w, _ in parts) / sum(w for _, w, _ in parts)
    confidence = 95 if a.destiny and b.destiny else 80
    return ScoreResult(clamp(total), confidence, [f for _, _, f in parts])
