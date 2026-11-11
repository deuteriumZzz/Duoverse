"""What the knowledge base should hold: every key the report and the daily layer can ask for, grouped for drafting.

`kb_coverage` counts against it, `kb_draft` writes drafts for the missing keys. Targets are set to beat a
generic couples app on what a pair sees every day (a year of questions, habits and exercises per sphere)
and to give every astrological contact a reviewed text instead of the generated grammar.
"""

from dataclasses import dataclass, field

from apps.astrology.domain.chart import HOUSE_AREA, POINTS, SIGNS
from apps.compatibility.domain.archetypes import DYNAMICS, ROLES

SPHERES = {
    "attraction": "Притяжение и близость",
    "sex": "Секс и телесность (18+, без откровенных описаний)",
    "emotions": "Эмоции и поддержка",
    "talk": "Общение и разговоры",
    "conflicts": "Конфликты и примирение",
    "trust": "Доверие и ревность",
    "power": "Власть, решения и контроль",
    "shadows": "Тени: старые раны, страхи, защиты",
    "home": "Дом, быт и ритм",
    "money": "Деньги и ценности",
    "plans": "Планы и будущее",
    "people": "Друзья, семья, окружение",
    "growth": "Рост и свобода каждого",
}
CATS = ["passion", "emotions", "communication", "values", "conflict", "home"]
TONES = ["synergy", "neutral", "attention", "risk"]
MAJOR = ["conj", "sextile", "square", "trine", "opp"]
CORE = ["Солнце", "Луна", "Меркурий", "Венера", "Марс", "Юпитер", "Сатурн", "Асцендент"]
PERSONAL = ["Солнце", "Луна", "Меркурий", "Венера", "Марс"]
SLOW = ["Уран", "Нептун", "Плутон", "Северный узел", "Лилит", "Хирон"]
BODIES = [p for p in POINTS if POINTS[p].kind != "angle"]
QUESTIONS_PER_SPHERE, HABITS_PER_SPHERE, EXERCISES_PER_SPHERE = 28, 6, 3
QUIZZES = 12  # one a week, a quarter without repeats
CASES = ["", "_gen", "_dat", "_acc", "_ins", "_pre"]  # Аня, Ани, Ане, Аню, Аней, Ане


def holders(*who: str) -> list[str]:
    return [w + c for w in who for c in CASES]


@dataclass(frozen=True)
class Group:
    """One drafting request: keys of the same kind, written together so they stay consistent and don't repeat."""

    kind: str  # text | question | habit | exercise
    domain: str
    keys: list[str]
    brief: str
    evidence: str = "symbolic"
    placeholders: list[str] = field(default_factory=list)


def _n(i: int) -> str:
    return f"{i:02d}"


def groups() -> list[Group]:
    out: list[Group] = []
    for sphere, title in SPHERES.items():
        out.append(
            Group(
                "question",
                "pair",
                [f"QUESTION:{sphere}:{_n(i)}" for i in range(1, QUESTIONS_PER_SPHERE + 1)],
                f"Вопросы дня для пары по сфере «{title}». Один вопрос — на двоих, каждый отвечает своими словами. "
                "Глубина 1 — лёгкие и тёплые, 2 — про чувства и привычки, 3 — про трудное (не больше трети). Не повторяйтесь.",
            )
        )
        out.append(
            Group(
                "habit",
                "pair",
                [f"HABIT:{sphere}:{_n(i)}" for i in range(1, HABITS_PER_SPHERE + 1)],
                f"Микропривычки для пары по сфере «{title}»: маленькие регулярные действия на 1–15 минут, которые реально "
                "делать вдвоём на неделе. Опирайтесь на исследования отношений (Готтман, теория привязанности, EFT), где уместно.",
                evidence="scientific",
            )
        )
        out.append(
            Group(
                "exercise",
                "pair",
                [f"EXERCISE:{sphere}:{_n(i)}" for i in range(1, EXERCISES_PER_SPHERE + 1)],
                f"Упражнения для пары по сфере «{title}» на 10–30 минут, 3–5 понятных шагов. В поле source укажите "
                "научную основу (автор или метод), если она есть, иначе пустую строку.",
                evidence="scientific",
            )
        )
    roles = sorted(ROLES)  # the report looks pair types up as PAIRTYPE:<min key>+<max key>
    for i, ra in enumerate(roles):
        for rb in roles[i:]:
            a, b = ROLES[ra], ROLES[rb]
            out.append(
                Group(
                    "text",
                    "pair",
                    [f"PAIRTYPE:{ra}+{rb}"],
                    f"Описание типа пары «{a.name} и {b.name}»: {a.name} {a.verb}, {b.name} {b.verb}. 4–5 предложений: на чём "
                    "держится такая пара, в чём её магия, где типичное напряжение и что помогает. Без имён людей.",
                )
            )
    pairs = [(pa, pb) for pa in CORE for pb in CORE if not (pa == pb == "Асцендент")]
    pairs += [(pa, pb) for pa in SLOW for pb in PERSONAL] + [(pa, pb) for pa in PERSONAL for pb in SLOW]
    for pa, pb in pairs:
        out.append(
            Group(
                "text",
                "astrology",
                [f"ASPECT:{pa}:{k}:{pb}" for k in MAJOR],
                f"Синастрия: {pa} человека {{a}} и {pb} человека {{b}} — по тексту на каждый мажорный аспект в порядке ключей "
                "(соединение, секстиль, квадрат, трин, оппозиция). 3–4 предложения: что это даёт паре в жизни, кому что "
                f"важно, как проявляется в быту и в ссоре, что помогает. Направление важно: {pa} у {{a_gen}}, {pb} у {{b_gen}}.",
                placeholders=holders("a", "b"),
            )
        )
    for body in BODIES:
        out.append(
            Group(
                "text",
                "astrology",
                [f"OVERLAY:{body}:{h}" for h in range(1, 13)],
                f"Наложение домов: {body} человека {{owner}} попадает в дом партнёра {{other}} — по тексту на дома 1–12 в порядке "
                "ключей (" + "; ".join(f"{h} — {HOUSE_AREA[h]}" for h in range(1, 13)) + "). 2–3 предложения: как {owner} "
                "влияет на эту сферу жизни {other_gen}.",
                placeholders=holders("owner", "other"),
            )
        )
    for point in POINTS:
        out.append(
            Group(
                "text",
                "astrology",
                [f"PLACEMENT:{point}:{s}" for s in SIGNS],
                f"«{point}» в каждом знаке зодиака (в порядке ключей) в карте человека {{name}}, глазами отношений: "
                "2–3 предложения, как это проявляется в любви и в паре.",
                placeholders=holders("name"),
            )
        )
        out.append(
            Group(
                "text",
                "astrology",
                [f"COMPOSITE:{point}:{s}" for s in SIGNS],
                f"Композитная карта пары: «{point}» композита в каждом знаке (в порядке ключей). 2 предложения о том, как это "
                "окрашивает союз как целое. Без имён.",
            )
        )
    return out


def expected_keys() -> list[str]:
    """Every key reports and the daily layer can use, including the hand-written core."""
    keys = [f"CAT:{c}:{t}" for c in CATS for t in TONES]
    keys += [f"INSIGHT:{c}:{k}" for c in CATS for k in ("good", "hard")]
    keys += [f"{p}:{c}" for p in ("RISK", "DAILY") for c in CATS]
    keys += [f"SPHERE:{s}" for s in SPHERES] + [f"ROLE:{r}" for r in ROLES] + [f"SUMMARY:{d}" for d in DYNAMICS]
    keys += [k for g in groups() for k in g.keys]
    keys += [f"QUIZ:{i:02d}" for i in range(1, QUIZZES + 1)]
    return keys
