"""«Календарь пары»: birthdays from the questionnaire, the day you met with its anniversaries and milestones, your own
dates with a note, and the holidays couples keep. Pure functions: the view and the evening job pass the data in.

A pair's own dates live encrypted on Pair.dates: [{"id", "kind": "met" | "custom", "title", "day": ISO, "note", "by"}].
"""

import secrets
from datetime import date, timedelta

from apps.core.domain.names import acc, gen

# (month, day, title, for whom): 23 февраля and 8 марта are for a person — when someone said they are «он» / «она»,
# the other partner hears about it; with no gender given they are shown and never pushed. Any pair: two women both hear
HOLIDAYS = (
    (2, 14, "День всех влюблённых", ""),
    (2, 23, "День защитника Отечества", "m"),
    (3, 8, "Международный женский день", "f"),
    (12, 31, "Новый год", ""),
)
MILESTONES = (100, 200, 300, 500, 777, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 7000, 10000)
REMIND = (7, 1)  # days before
MAX_ENTRIES, TITLE_MAX, NOTE_MAX = 40, 60, 200


def plural(n: int, one: str, few: str, many: str) -> str:
    n10, n100 = n % 10, n % 100
    return one if n10 == 1 and n100 != 11 else few if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else many


def years(n: int) -> str:
    return f"{n} {plural(n, 'год', 'года', 'лет')}"


def yearly(d: date, today: date) -> date:
    """The next time this month and day come round, today included; 29 February falls on the 28th in other years."""
    for y in (today.year, today.year + 1):
        try:
            nxt = d.replace(year=y)
        except ValueError:
            nxt = date(y, 2, 28)
        if nxt >= today:
            return nxt
    raise AssertionError("unreachable")


def people(pair) -> list[tuple[str, str, str, str]]:
    """Both partners as upcoming() takes them: side, name, birthday, gender ("f" / "m" / "")."""
    return [("a", pair.a.name, pair.a.birth["date"], pair.a.gender), ("b", pair.b.name, pair.b.birth["date"], pair.b.gender)]


def met_day(entries: list[dict]) -> date | None:
    return next((date.fromisoformat(e["day"]) for e in entries if e.get("kind") == "met"), None)


def upcoming(today: date, people: list[tuple[str, str, str]], entries: list[dict], horizon: int = 365) -> list[dict]:
    """people: [(side, name, birth ISO)] → the pair's dates within `horizon` days, soonest first:
    {"day", "in", "kind", "title", "sub", "note", "side", "name", "id", "quiet"}."""
    out: list[dict] = []

    def add(day: date, kind: str, title: str, **extra) -> None:
        if 0 <= (day - today).days <= horizon:
            blank = {"sub": "", "note": "", "side": "", "name": "", "id": "", "quiet": False}
            out.append({"day": day, "in": (day - today).days, "kind": kind, "title": title, **blank, **extra})

    for side, name, born, *_ in people:
        b = date.fromisoformat(born)
        nxt = yearly(b, today)
        add(nxt, "birthday", f"День рождения {gen(name)}", sub=years(nxt.year - b.year), side=side, name=name)
    if met := met_day(entries):
        nxt = yearly(met, today)
        if nxt.year > met.year:
            add(nxt, "met", "Годовщина знакомства", sub=years(nxt.year - met.year))
        for n in MILESTONES:
            add(met + timedelta(days=n), "milestone", f"{n} {plural(n, 'день', 'дня', 'дней')} со знакомства")
    for e in entries:
        if e.get("kind") != "custom":
            continue
        d = date.fromisoformat(e["day"])
        nxt = d if d >= today else yearly(d, today)  # a date ahead happens once; a past one comes back every year
        add(nxt, "custom", e["title"], sub=years(nxt.year - d.year) if nxt.year > d.year else "", note=e.get("note", ""), id=e["id"])
    for m, d, title, whom in HOLIDAYS:
        day = yearly(date(today.year, m, d), today)
        for_them = [(side, name) for side, name, _, *g in people if whom and g and g[0] == whom]
        if not whom or not for_them:
            add(day, "holiday", title, quiet=bool(whom))
        for side, name in for_them:
            add(day, "holiday", title, side=side, name=name)
    return sorted(out, key=lambda e: e["day"])


def together(today: date, entries: list[dict]) -> int | None:
    """Days since you met, or None until the day is set."""
    met = met_day(entries)
    return (today - met).days if met else None


def road(together: int) -> dict:
    """The calendar's hero: the road from the day you met, with the last few milestones passed and the next one ahead,
    placed on 0…next along x 40…290 of a 320-wide scene."""
    nxt = next((m for m in MILESTONES if m > together), None)
    end = nxt or max(together, 1)

    def x(days: int) -> int:
        return round(40 + 250 * min(days, end) / end)

    flags = [{"x": x(m), "n": m, "done": True} for m in MILESTONES if m <= together][-4:]
    if nxt:
        flags.append({"x": x(nxt), "n": nxt, "done": False})
    return {"today_x": x(together), "flags": flags, "next": nxt, "left": nxt - together if nxt else 0}


def due(events: list[dict]) -> list[dict]:
    """What to remind about today: a week and a day before, holidays only if they are for everyone."""
    return [e for e in events if e["in"] in REMIND and not e["quiet"]]


def recipients(event: dict) -> set[str]:
    """Sides to tell; a birthday (or 8 марта / 23 февраля) goes only to the other partner, so the surprise stays one."""
    if event["kind"] == "birthday" or (event["kind"] == "holiday" and event["side"]):
        return {"b" if event["side"] == "a" else "a"}
    return {"a", "b"}


def reminder_text(event: dict, ideas: tuple[int, int] | None = None) -> str:
    """ideas: (gift ideas in the birthday person's wish map, how many are still free) — wishes.ideas_for."""
    when = "Через неделю" if event["in"] == 7 else "Завтра"
    kind = event["kind"]
    if kind == "birthday":
        text = f"{when} день рождения у {gen(event['name'])} — {event['sub']}."
        n, free = ideas or (0, 0)
        if not n:
            return text + " Самое время подумать о подарке."
        taken = ", одну вы уже забронировали" if n - free == 1 else f", {n - free} вы уже забронировали" if n > free else ""
        return text + f" В карте желаний {n} {plural(n, 'идея', 'идеи', 'идей')}{taken}."
    if kind == "holiday" and event["name"]:
        return f"{when} {event['title']} — порадуйте {acc(event['name'])}."
    if event["title"] == "День всех влюблённых":
        return f"{when} День всех влюблённых. Можно подарить друг другу полный разбор пары — или придумать что-нибудь для двоих."
    if kind == "met":
        return f"{when} годовщина вашего знакомства — {event['sub']}."
    if kind == "milestone":
        return f"{when} {event['title']}. Хороший повод для маленького праздника."
    if kind == "custom":
        return f"{when} — «{event['title']}»" + (f", {event['sub']}" if event["sub"] else "") + "."
    return f"{when} — {event['title']}. Придумайте что-нибудь для двоих."


def clean(form: dict[str, str], today: date, side: str) -> dict | None:
    """A date from the form, or None if it doesn't hold: a known kind, a real day (the day you met is not ahead,
    your own dates go at most a year ahead and a century back), titles and notes cut to size."""
    kind = form.get("kind", "custom")
    try:
        day = date.fromisoformat(form.get("day", "").strip())
    except ValueError:
        return None
    title = " ".join(form.get("title", "").split())[:TITLE_MAX]
    if kind == "met":
        title = "День знакомства"
    if kind not in ("met", "custom") or not title or day.year < today.year - 100:
        return None
    if day > (today if kind == "met" else today + timedelta(days=365)):
        return None
    note = " ".join(form.get("note", "").split())[:NOTE_MAX]
    return {"id": secrets.token_hex(4), "kind": kind, "title": title, "day": day.isoformat(), "note": note, "by": side}


if __name__ == "__main__":
    today = date(2026, 11, 25)
    assert yearly(date(1996, 3, 14), today) == date(2027, 3, 14) and yearly(date(1990, 11, 25), today) == today
    assert yearly(date(2000, 2, 29), date(2027, 1, 1)) == date(2027, 2, 28)
    assert [plural(n, "год", "года", "лет") for n in (1, 2, 5, 11, 21, 104, 112)] == ["год", "года", "лет", "лет", "год", "года", "лет"]
    met = {"id": "m", "kind": "met", "title": "День знакомства", "day": "2024-03-02", "note": "", "by": "a"}
    trip = {"id": "t", "kind": "custom", "title": "Поездка в Казань", "day": "2027-05-01", "note": "билеты в почте", "by": "b"}
    wed = {"id": "w", "kind": "custom", "title": "Свадьба", "day": "2025-12-02", "note": "", "by": "a"}
    ev = upcoming(today, [("a", "Аня", "1996-12-02"), ("b", "Миша", "1994-03-14")], [met, trip, wed])
    by = {e["title"]: e for e in ev}
    assert by["День рождения Ани"]["in"] == 7 and by["День рождения Ани"]["sub"] == "30 лет"
    assert by["Свадьба"]["sub"] == "1 год" and by["Поездка в Казань"]["day"] == date(2027, 5, 1)
    assert by["1000 дней со знакомства"]["day"] == date(2026, 11, 27) and by["Годовщина знакомства"]["sub"] == "3 года"
    assert [e["day"] for e in ev] == sorted(e["day"] for e in ev) and together(today, [met]) == 998
    soon = due(ev)
    assert {e["title"] for e in soon} == {"День рождения Ани", "Свадьба"}  # 7 days; the 1000th day is in 2, not 1 or 7
    assert recipients(by["День рождения Ани"]) == {"b"} and recipients(by["Свадьба"]) == {"a", "b"}
    assert reminder_text(by["День рождения Ани"]).startswith("Через неделю день рождения у Ани — 30 лет")
    assert reminder_text(by["День рождения Ани"], (4, 3)).endswith("В карте желаний 4 идеи, одну вы уже забронировали.")
    assert reminder_text(by["День рождения Ани"], (5, 5)).endswith("В карте желаний 5 идей.")
    assert not any(e["title"] == "8 марта" for e in due(upcoming(date(2027, 3, 1), [], [])))  # no gender given: never pushed
    pair = [("a", "Аня", "1996-12-02", "f"), ("b", "Миша", "1994-03-14", "m")]
    womens = [e for e in due(upcoming(date(2027, 3, 1), pair, [])) if e["title"] == "8 марта"]
    assert len(womens) == 1 and recipients(womens[0]) == {"b"} and reminder_text(womens[0]) == "Через неделю 8 марта — порадуйте Аню."
    girls = [("a", "Аня", "1996-12-02", "f"), ("b", "Оля", "1995-01-01", "f")]
    two = [e for e in upcoming(date(2027, 3, 1), girls, []) if e["title"] == "8 марта"]
    assert {e["name"] for e in two} == {"Аня", "Оля"} and {s for e in two for s in recipients(e)} == {"a", "b"}  # any pair
    r = road(993)
    assert r["next"] == 1000 and r["left"] == 7 and r["flags"][-1]["x"] == 290
    assert [f["n"] for f in r["flags"]] == [200, 300, 500, 777, 1000]
    assert road(20)["flags"] == [{"x": 290, "n": 100, "done": False}] and road(20)["today_x"] == 90 and road(20000)["next"] is None
    assert clean({"kind": "met", "day": "2030-01-01"}, today, "a") is None  # you can't have met in the future
    assert clean({"title": "  Первый   поцелуй ", "day": "2024-06-12"}, today, "b")["title"] == "Первый поцелуй"
    assert clean({"title": "x", "day": "12.06.2024"}, today, "a") is None and clean({"title": "", "day": "2024-06-12"}, today, "a") is None
    print("ok")
