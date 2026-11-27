"""«История пары»: what happened to a pair, in order — reports with how the score moved, the partner joining, the pair week,
the full report opened, what appeared on the tree — plus which spheres changed most between the first and the latest
report. Built from what is already stored; only the day each thing appeared on the tree is noted for it.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

RECHECK_AFTER = timedelta(days=90)  # a fresh look at the pair: questionnaires again, a new report, the change shown


@dataclass(frozen=True)
class Event:
    when: date
    icon: str
    title: str
    detail: str = ""


def _day(d: date | datetime) -> date:
    return d.date() if isinstance(d, datetime) else d


def events(
    reports: list[dict], joined: datetime | None, week: dict | None, opened: datetime | None, tree: dict | None = None
) -> list[Event]:
    """reports: [{"created_at", "score", "pair_type"}] oldest first; week: pair.plan["week"] or None; tree:
    pair.plan["tree"], {mark: [day, title]} — the day each thing first appeared on the tree (tree.MARKS)."""
    out = []
    prev = None
    for i, r in enumerate(reports):
        if i == 0:
            out.append(Event(_day(r["created_at"]), "sparkles", "Первый разбор пары", f"{r['pair_type']} · {r['score']}/100"))
        else:
            delta = r["score"] - prev
            move = f"{'+' if delta > 0 else ''}{delta} к прошлому" if delta else "балл тот же"
            out.append(Event(_day(r["created_at"]), "refresh-cw", "Новый разбор", f"{r['score']}/100 · {move}"))
        prev = r["score"]
    if joined:
        out.append(Event(_day(joined), "heart-handshake", "Вы стали парой в Duoverse", "разбор, план и вопрос дня — общие"))
    if opened:
        out.append(Event(_day(opened), "lock-open", "Открыли полный разбор", "все сферы, сценарии и «Неделя пары»"))
    if week:
        out.append(Event(date.fromisoformat(week["started"]), "calendar-days", "Начали «Неделю пары»", "7 шагов из вашего разбора"))
        both = sum(1 for marks in week.get("done", {}).values() if {"a", "b"} <= set(marks))
        if both == len(week.get("days", [])) and both:
            out.append(Event(date.fromisoformat(week["started"]) + timedelta(days=6), "trophy", "Прошли неделю пары вдвоём"))
    out += [Event(date.fromisoformat(day), "sprout", title, "на вашем дереве") for day, title in (tree or {}).values()]
    return sorted(out, key=lambda e: e.when, reverse=True)


def changes(first: list[dict], last: list[dict], top: int = 3) -> list[dict]:
    """Spheres that moved most between two reports: [{"title", "from", "to", "delta"}], biggest change first."""
    before = {s["key"]: s["score"] for s in first}
    moved = [
        {"title": s["title"], "from": before[s["key"]], "to": s["score"], "delta": s["score"] - before[s["key"]]}
        for s in last
        if s["key"] in before and s["score"] != before[s["key"]]
    ]
    return sorted(moved, key=lambda m: -abs(m["delta"]))[:top]


def recheck_due(last_report: datetime, now: datetime) -> bool:
    return now - last_report >= RECHECK_AFTER


if __name__ == "__main__":
    r = [
        {"created_at": datetime(2026, 1, 10), "score": 70, "pair_type": "Парус и компас"},
        {"created_at": datetime(2026, 4, 12), "score": 76, "pair_type": "Парус и компас"},
    ]
    week = {"started": "2026-02-01", "days": [{}] * 7, "done": {str(n): ["a", "b"] for n in range(1, 8)}}
    ev = events(r, datetime(2026, 1, 11), week, datetime(2026, 1, 20))
    assert ev[0].title == "Новый разбор" and "+6 к прошлому" in ev[0].detail and ev[-1].title == "Первый разбор пары"
    assert any(e.title == "Прошли неделю пары вдвоём" for e in ev)
    assert events([], None, None, None, {"nest": ["2026-05-01", "Птица свила гнездо"]})[0].title == "Птица свила гнездо"
    ch = changes([{"key": "money", "title": "Деньги", "score": 40}, {"key": "home", "title": "Дом", "score": 60}],
                 [{"key": "money", "title": "Деньги", "score": 55}, {"key": "home", "title": "Дом", "score": 58}])  # fmt: skip
    assert ch[0] == {"title": "Деньги", "from": 40, "to": 55, "delta": 15} and len(ch) == 2
    assert recheck_due(datetime(2026, 1, 1), datetime(2026, 4, 2)) and not recheck_due(datetime(2026, 1, 1), datetime(2026, 2, 1))
    print("ok")
