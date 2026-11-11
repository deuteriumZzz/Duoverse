"""Genitive and dative of Russian first names, so texts read «у Ани», «Мише важно».

ponytail: rule-based for common first names; unknown shapes (Latin, -о/-е/-и/-у endings, two words) stay as typed.
Feminine soft-sign names (Любовь, Нинель) decline as masculine — add an exception list if users hit it.
"""

import re

_HUSH = set("гкхжшщч")


def _decline(name: str, case: str) -> str:
    if not re.fullmatch(r"[А-ЯЁ][а-яё]+(-[А-ЯЁ][а-яё]+)?", name):
        return name
    stem, end = name[:-1], name[-1]
    hush = stem[-1] in "жшчщц"
    if end in "ая":
        soft = end == "я"
        if stem.endswith("и") and soft:  # Мария
            return stem + {"gen": "и", "dat": "и", "acc": "ю", "ins": "ей", "pre": "и"}[case]
        if case == "gen":
            return stem + ("и" if soft or stem[-1] in _HUSH else "ы")
        return stem + {"dat": "е", "acc": "ю" if soft else "у", "ins": "ей" if soft or hush else "ой", "pre": "е"}[case]
    if end in "йь":
        return stem + {"gen": "я", "dat": "ю", "acc": "я", "ins": "ем", "pre": "е"}[case]
    if end in "оеиуыэю":
        return name
    return name + {"gen": "а", "dat": "у", "acc": "а", "ins": "ем" if name[-1] in "жшчщц" else "ом", "pre": "е"}[case]


def gen(name: str) -> str:
    return _decline(name, "gen")


def dat(name: str) -> str:
    return _decline(name, "dat")


def forms(name: str) -> dict[str, str]:
    """All case forms used by knowledge texts: «{x}», «{x_gen}» (у Ани), «{x_dat}» (Ане), «{x_acc}» (Аню),
    «{x_ins}» (с Аней), «{x_pre}» (об Ане)."""
    return {"": name, **{f"_{c}": _decline(name, c) for c in ("gen", "dat", "acc", "ins", "pre")}}


if __name__ == "__main__":
    pairs = {
        "Аня": ("Ани", "Ане"),
        "Миша": ("Миши", "Мише"),
        "Маша": ("Маши", "Маше"),
        "Ольга": ("Ольги", "Ольге"),
        "Мария": ("Марии", "Марии"),
        "Иван": ("Ивана", "Ивану"),
        "Андрей": ("Андрея", "Андрею"),
        "Игорь": ("Игоря", "Игорю"),
        "Лена": ("Лены", "Лене"),
        "Alex": ("Alex", "Alex"),
        "Анри": ("Анри", "Анри"),
    }
    for n, (g, d) in pairs.items():
        assert (gen(n), dat(n)) == (g, d), (n, gen(n), dat(n))
    print("ok")
