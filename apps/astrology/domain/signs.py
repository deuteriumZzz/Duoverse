"""Sun-sign compatibility: the angle between two signs decides it (the classical aspect read)."""

from apps.astrology.domain.chart import SIGN_ELEMENT, SIGNS

# distance in signs (0..6) -> (aspect, what it tends to feel like). No scores: one sign is one of many chart points,
# so the page groups kinds of connection instead of ranking people.
BY_DISTANCE = {
    0: ("один знак", "понимаете друг друга с полуслова, а сильные и слабые стороны у вас общие"),
    1: ("соседние знаки", "разные ритмы и ценности: интересно, но нужно учиться языку друг друга"),
    2: ("секстиль", "лёгкое взаимодействие и общие интересы, стихии-союзники"),
    3: ("квадрат", "трение и вызов: искры летят, и именно в спорах вы растёте"),
    4: ("трин", "одна стихия: естественное понимание и поддержка"),
    5: ("квинконс", "разные языки: ожидания лучше проговаривать, а не угадывать"),
    6: ("оппозиция", "притяжение противоположностей: вы дополняете друг друга"),
}
GROUPS = [  # key, title, what it means, distances
    ("easy", "Легко находите общий язык", "Похожий темп или стихии-союзники: понимание приходит без лишних слов.", (4, 2, 0)),
    (
        "opposites",
        "Притяжение разных",
        "Противоположности, которые дополняют друг друга: много интереса и много поводов договариваться.",
        (6,),
    ),
    (
        "agree",
        "Нужны договорённости",
        "Разные ритмы и ожидания. Это не «плохая пара»: такие связи держатся на том, что вы проговариваете вслух.",
        (3, 1, 5),
    ),
]


# Distance is a zodiac relation class; the detailed text lives in the reviewed knowledge base.
SUNPAIR_RELATIONS = {
    0: "conjunction",
    1: "neighbor",
    2: "sextile",
    3: "square",
    4: "trine",
    5: "quincunx",
    6: "opposition",
}


def relation_key(a: int, b: int) -> str:
    distance = min((a - b) % 12, (b - a) % 12)
    return f"SUNPAIR:{SUNPAIR_RELATIONS[distance]}"


def distance(a: int, b: int) -> int:
    return min((a - b) % 12, (b - a) % 12)


def groups(sign: int) -> list[dict]:
    """The 12 signs against `sign`, grouped by kind of connection; within a group, in zodiac order from `sign`."""
    out = []
    for key, title, about, distances in GROUPS:
        members = [c for c in ((sign + k) % 12 for k in range(12)) if distance(sign, c) in distances]
        members.sort(key=lambda c: (distances.index(distance(sign, c)), (c - sign) % 12))
        out.append(
            {
                "key": key,
                "title": title,
                "about": about,
                "signs": [
                    {
                        "idx": c,
                        "name": SIGNS[c],
                        "element": SIGN_ELEMENT[c],
                        "label": BY_DISTANCE[distance(sign, c)][0],
                        "why": BY_DISTANCE[distance(sign, c)][1],
                        "knowledge_key": relation_key(sign, c),
                    }
                    for c in members
                ],
            }
        )
    return out


def demo() -> None:
    g = {x["key"]: [s["name"] for s in x["signs"]] for x in groups(SIGNS.index("Овен"))}
    assert g["easy"][:2] == ["Лев", "Стрелец"] and "Овен" in g["easy"]  # the fire trine first, then sextiles, then itself
    assert g["opposites"] == ["Весы"]
    assert sum(len(v) for v in g.values()) == 12


if __name__ == "__main__":
    demo()
