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
    gen = case == "gen"
    if end == "а":
        return stem + (("и" if stem[-1] in _HUSH else "ы") if gen else "е")
    if end == "я":
        return stem + ("и" if gen or stem.endswith("и") else "е")
    if end == "й":
        return stem + ("я" if gen else "ю")
    if end == "ь":
        return stem + ("я" if gen else "ю")
    if end in "оеиуыэю":
        return name
    return name + ("а" if gen else "у")


def gen(name: str) -> str:
    return _decline(name, "gen")


def dat(name: str) -> str:
    return _decline(name, "dat")


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
