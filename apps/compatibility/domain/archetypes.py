"""Pair typology: each partner gets one of 12 roles, the pair is role A × role B × dynamic.

Role = element (where the energy lives) × mode (how it moves). In a full report the element comes from the
dominant element across Sun, Moon, Venus and Mars and the mode is refined by psychology; with dates only we use
the Sun sign and the life-path number. 12 roles → 78 unordered pair types (144 ordered portraits: who is A matters for
colours and wording). The dynamic is derived from the two elements, so it adds no extra combinations.
Pure functions, no Django — the real scorer will call the same code.
"""

from dataclasses import dataclass

ELEMENTS = {"fire": "огонь", "earth": "земля", "air": "воздух", "water": "вода"}
MODES = {"initiator": "инициатор", "keeper": "хранитель", "conductor": "проводник"}


@dataclass(frozen=True)
class Role:
    key: str
    name: str
    plural: str  # «Два костра» — for a pair of the same role
    verb: str  # what this partner brings: «задаёт направление»
    element: str
    mode: str


ROLES = {
    r.key: r
    for r in [
        Role("spark", "Искра", "Две искры", "зажигает новое", "fire", "initiator"),
        Role("fire", "Костёр", "Два костра", "греет и собирает вокруг себя", "fire", "keeper"),
        Role("star", "Звезда", "Две звезды", "вдохновляет и ведёт", "fire", "conductor"),
        Role("compass", "Компас", "Два компаса", "задаёт направление", "earth", "initiator"),
        Role("mountain", "Гора", "Две горы", "держит опору", "earth", "keeper"),
        Role("garden", "Сад", "Два сада", "растит и заботится", "earth", "conductor"),
        Role("bridge", "Мост", "Два моста", "соединяет и договаривается", "air", "initiator"),
        Role("lighthouse", "Маяк", "Два маяка", "видит дальше и светит другому", "air", "keeper"),
        Role("wind", "Ветер", "Два ветра", "приносит перемены", "air", "conductor"),
        Role("river", "Река", "Две реки", "чувствует течение", "water", "initiator"),
        Role("harbor", "Гавань", "Две гавани", "даёт безопасность", "water", "keeper"),
        Role("sail", "Парус", "Два паруса", "ловит ветер перемен", "water", "conductor"),
    ]
}
GRID = {(r.element, r.mode): r for r in ROLES.values()}


@dataclass(frozen=True)
class Dynamic:
    key: str
    title: str
    text: str


DYNAMICS = {
    d.key: d
    for d in [
        Dynamic("resonance", "Резонанс", "Одна стихия: вы усиливаете друг друга — и сильные стороны, и слабые."),
        Dynamic("complement", "Дополнение", "Стихии питают друг друга: то, чего не хватает одному, есть у другого."),
        Dynamic("contrast", "Контраст", "Противоположные стихии: сильное притяжение и необходимость договариваться."),
        Dynamic("friction", "Притирка", "Стихии не мешают, но и не подсказывают: общий ритм находится со временем."),
    ]
}
_COMPLEMENT = {frozenset({"fire", "air"}), frozenset({"earth", "water"})}
_CONTRAST = {frozenset({"fire", "water"}), frozenset({"earth", "air"})}

SIGN_ELEMENT = {
    "Овен": "fire",
    "Лев": "fire",
    "Стрелец": "fire",
    "Телец": "earth",
    "Дева": "earth",
    "Козерог": "earth",
    "Близнецы": "air",
    "Весы": "air",
    "Водолей": "air",
    "Рак": "water",
    "Скорпион": "water",
    "Рыбы": "water",
}


def mode_from_life_path(n: int) -> str:
    """1·4·7 начинают, 2·5·8 удерживают, 3·6·9 проводят. Master numbers reduce first (11→2, 22→4, 33→6)."""
    while n > 9:
        n = sum(int(c) for c in str(n))
    return {1: "initiator", 4: "initiator", 7: "initiator", 2: "keeper", 5: "keeper", 8: "keeper"}.get(n, "conductor")


def role_for(element: str, mode: str) -> Role:
    return GRID[(element, mode)]


def dynamic_for(a: Role, b: Role) -> Dynamic:
    pair = frozenset({a.element, b.element})
    if a.element == b.element:
        return DYNAMICS["resonance"]
    return DYNAMICS["complement"] if pair in _COMPLEMENT else DYNAMICS["contrast"] if pair in _CONTRAST else DYNAMICS["friction"]


def pair_name(a: Role, b: Role) -> str:
    return a.plural if a.key == b.key else f"{a.name} и {b.name.lower()}"


def pair_tagline(a: Role, b: Role, name_a: str, name_b: str) -> str:
    if a.key == b.key:
        return f"{name_a} и {name_b} оба {a.verb.split(' и ')[0]} — вместе вдвое сильнее"
    return f"{name_a} {a.verb}, {name_b} — {b.verb}"


if __name__ == "__main__":
    names = {pair_name(a, b) for a in ROLES.values() for b in ROLES.values()}
    assert len(GRID) == 12 and len(names) == 144, len(names)
    assert mode_from_life_path(33) == "conductor" and mode_from_life_path(7) == "initiator" and mode_from_life_path(29) == "keeper"
    assert dynamic_for(ROLES["sail"], ROLES["compass"]).key == "complement"
    assert dynamic_for(ROLES["spark"], ROLES["harbor"]).key == "contrast"
    print("ok:", len(names), "pair names")
