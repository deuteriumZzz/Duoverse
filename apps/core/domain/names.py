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


def acc(name: str) -> str:
    return _decline(name, "acc")


def inflect(text: str, gender: str) -> str:
    """«{ответил|ответила|ответил(а)}» → the form for "m", "f", or the neutral one when we don't know: past-tense verbs
    in Russian change with who did it, and a person may not have said. Short forms like «рад(а)» follow too (agree)."""
    text = re.sub(r"\{([^{}|]+)\|([^{}|]+)\|([^{}|]+)\}", lambda m: m[1] if gender == "m" else m[2] if gender == "f" else m[3], text)
    return agree(text, gender)


_ODD = {"ответствен": "ответственна", "спокоен": "спокойна", "один": "одна"}
# written «злопамятн(а)» in the knowledge base: the stem, not the masculine — he is «злопамятен», «чуток»
_MASC = {"злопамятн": "злопамятен", "чувствительн": "чувствителен", "надёжн": "надёжен", "колк": "колок", "чутк": "чуток"}


def gendered(word: str, ending: str) -> tuple[str, str] | None:
    """«хотел», «а» → ("хотел", "хотела"): the masculine and feminine of a word written as «хотел(а)» in our texts.
    None for an ending we don't know — such a word stays as written. Every form in the knowledge base is covered
    (tests/test_knowledge_draft.py checks it)."""
    w, low = word, word.lower()
    if ending == "ым" and low.endswith("ой"):  # «понятой(ым)»: written feminine first
        return w[:-2] + "ым", w
    if low in _ODD and ending in ("на", "одна"):
        f = _ODD[low]
        f = f.capitalize() if w[0].isupper() else f
    elif ending == "а":
        f = (w[:-2] + "е" + w[-1] if low.endswith(("ёл", "ён")) else w) + "а"  # вёл → вела, напряжён → напряжена
    elif ending == "ла":
        f = (w[:-2] if low.endswith("ёл") else w) + "ла"  # прошёл → прошла, мог → могла
    elif ending in ("ой", "ей") and low.endswith(("ым", "им")):
        f = w[:-2] + ("ей" if low[-3:-2] in "жшщчц" else ending)  # поучающим → поучающей
    elif ending == "ой" and low.endswith(("ому", "ого")):
        f = w[:-3] + "ой"
    elif ending == "на" and low.endswith("ен"):
        f = w[:-2] + "на"
    elif ending == "льна" and low.endswith("лен"):
        f = w[:-3] + "льна"
    elif ending == "ка" and low.endswith("ок"):
        f = w[:-2] + "ка"
    elif ending == "ась" and low.endswith("ся"):
        f = w[:-2] + "ась"
    elif ending == "лась" and low.endswith("ся"):
        f = (w[:-3] if low.endswith("лся") else w[:-2]) + "лась"  # научился → научилась, ошибся → ошиблась
    else:
        return None
    m = _MASC.get(low, w)
    return (m.capitalize() if w[0].isupper() else m), f


FORM = re.compile(r"([А-ЯЁа-яё]+)\(([а-яё]+)\)")


def agree(text: str, gender: str = "", **who: str) -> str:
    """«ты хотел(а)» → «ты хотела» / «ты хотел» when the gender is known, as written when it isn't. With `who`
    (a="f", b="m") each form follows the nearest {a} or {b} before it: «{b} … незамеченным(ой), а {a} — сдерживаемым(ой)».
    Inside «…» (someone's own words) a form stays as written: there «ты» may be either of them.
    ponytail: nearest-subject heuristic — a clause whose subject is only a {b_gen}-style form keeps the last {a}/{b}."""
    subjects = [(m.start(), m[1]) for m in re.finditer(r"\{([a-z]+)\}", text) if m[1] in who] if who else []

    def one(m: re.Match) -> str:
        g = gender
        if who:
            before = [name for pos, name in subjects if pos < m.start()]
            quoted = text.count("«", 0, m.start()) > text.count("»", 0, m.start())  # «…чтобы ты выслушал(а)»: someone's words
            g = who[before[-1]] if before and not quoted else ""
        pair = gendered(m[1], m[2]) if g in ("m", "f") else None
        return m[0] if pair is None else pair[0] if g == "m" else pair[1]

    return FORM.sub(one, text)


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
    assert inflect("{Миша|Аня|Кто-то} {ответил|ответила|ответил(а)}", "f") == "Аня ответила"
    assert inflect("{прошёл|прошла|прошёл(ла)}", "") == "прошёл(ла)" and inflect("{он|она|он(а)}", "m") == "он"
    for n, (g, d) in pairs.items():
        assert (gen(n), dat(n)) == (g, d), (n, gen(n), dat(n))
    fem = {
        "хотел(а)": "хотела", "вёл(а)": "вела", "напряжён(а)": "напряжена", "надёжн(а)": "надёжна", "Сам(а)": "Сама",
        "прошёл(ла)": "прошла", "мог(ла)": "могла", "холодным(ой)": "холодной", "Каким(ой)": "Какой", "хорошим(ей)": "хорошей",
        "одному(ой)": "одной", "прямого(ой)": "прямой", "согласен(на)": "согласна", "спокоен(на)": "спокойна",
        "ответствен(на)": "ответственна", "внимателен(льна)": "внимательна", "резок(ка)": "резка", "один(одна)": "одна",
        "родился(ась)": "родилась", "научился(лась)": "научилась", "ошибся(лась)": "ошиблась", "понятой(ым)": "понятой",
    }  # fmt: skip
    for written, f in fem.items():
        assert agree(written, "f") == f, (written, agree(written, "f"))
    assert agree("понятой(ым)", "m") == "понятым" and agree("согласен(на)", "m") == "согласен"
    assert agree("поучающим(ой)", "f") == "поучающей" and agree("он злопамятн(а) и чутк(а)", "m") == "он злопамятен и чуток"
    assert agree("ты хотел(а)", "") == "ты хотел(а)" and agree("вселенная(ые) (CC BY)", "f") == "вселенная(ые) (CC BY)"
    two = "{b} может чувствовать себя незамеченным(ой), а {a} — сдерживаемым(ой)."
    assert agree(two, a="m", b="f") == "{b} может чувствовать себя незамеченной, а {a} — сдерживаемым."
    assert agree(two, a="m", b="") == "{b} может чувствовать себя незамеченным(ой), а {a} — сдерживаемым."
    assert inflect("{Миша|Аня|Кто-то} {ответил|ответила|ответил(а)} и рад(а)", "f") == "Аня ответила и рада"
    print("ok")
