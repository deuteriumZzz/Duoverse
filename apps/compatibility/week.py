# ruff: noqa: E501 — step copy reads best one phrase per line
"""«Неделя пары»: seven small steps built from a report — talks and exercises for the pair's weakest spheres — that
both partners mark in «Сегодня». Stored as JSON on the pair (plan["week"]); day 1 is free, the rest come with the
full report.
"""

import hashlib
from collections.abc import Callable
from datetime import date

KINDS = {"talk": "Разговор", "exercise": "Упражнение", "habit": "Маленький шаг", "reflect": "Итог недели"}
FREE_DAYS = 1


def _pick(items: list[dict], seed: str, depth: int | None = None, shift: int = 0) -> dict:
    """One item for this pair, the same every time; `shift` (the week's number) walks on, so a new week brings the next
    question or exercise of a sphere instead of repeating, until the sphere's pool comes round again."""
    pool = [i for i in items if depth is None or i.get("depth") == depth] or items
    if not pool:
        return {}
    return pool[(int(hashlib.sha256(seed.encode()).hexdigest(), 16) + shift) % len(pool)]


def build(
    spheres: list[tuple[str, str, int]], scenario: str, series: Callable[[str], list[dict]], seed: str, round_: int = 0
) -> list[dict]:
    """spheres: (key, title, score) of the report; the three weakest get the week. Deterministic for a given seed;
    `round_` is which week this is for the pair (0, 1, 2…): each one picks the next talks and exercises."""
    weak = sorted(spheres, key=lambda s: s[2])[:3] or [("talk", "Общение и разговоры", 0)]
    while len(weak) < 3:
        weak.append(weak[0])
    days: list[dict] = []

    def add(kind: str, sphere: tuple[str, str, int], title: str, text: str, steps: list[str] | None = None, minutes: int = 15) -> None:
        days.append({"n": len(days) + 1, "kind": kind, "kind_title": KINDS[kind], "sphere": sphere[0], "sphere_title": sphere[1],
                     "title": title, "text": text, "steps": steps or [], "minutes": minutes})  # fmt: skip

    def talk(sphere: tuple[str, str, int], depth: int, intro: str) -> None:
        q = _pick(series(f"QUESTION:{sphere[0]}:"), f"{seed}:{sphere[0]}:{depth}", depth, round_)
        add("talk", sphere, q.get("question", "Что для тебя сейчас самое важное в наших отношениях?"), intro, minutes=15)

    def exercise(sphere: tuple[str, str, int]) -> None:
        e = _pick(series(f"EXERCISE:{sphere[0]}:"), f"{seed}:{sphere[0]}:ex", shift=round_)
        if e:
            add(
                "exercise",
                sphere,
                e["title"],
                e.get("source", "") or "Упражнение из вашего разбора",
                e.get("steps", []),
                e.get("minutes", 20),
            )
        else:
            talk(sphere, 2, "Сегодня поговорите чуть глубже.")

    s1, s2, s3 = weak
    hint = f" В разборе у вас есть сценарий «{scenario}» — держите его в голове." if scenario else ""
    talk(s1, 1, f"Начнём с самой чувствительной для вас сферы — «{s1[1]}». Задайте друг другу этот вопрос и просто выслушайте.{hint}")
    exercise(s1)
    talk(s2, 2, f"Сфера «{s2[1]}». Отвечайте по очереди, без советов — только «понимаю» и уточняющие вопросы.")
    exercise(s2)
    h = _pick(series(f"HABIT:{s3[0]}:"), f"{seed}:{s3[0]}:habit", shift=round_)
    if h:
        add("habit", s3, h["title"], h.get("why", ""), [f"{h.get('cadence', '')} · {h.get('duration', '')}".strip(" ·")], 10)
    else:
        talk(s3, 1, f"Сфера «{s3[1]}».")
    exercise(s3)
    add("reflect", s1, "Что изменилось за неделю?", "Вспомните вместе: какой шаг дался легче всего, какой — труднее, и что хочется оставить как привычку.",
        ["Назовите по одному моменту недели, за который вы благодарны партнёру.", "Выберите один шаг, который повторите на следующей неделе."], 20)  # fmt: skip
    return days[:7]


def finished(week: dict, today: date) -> bool:
    """Seven days have passed since the week started: time for the next one."""
    return (today - date.fromisoformat(week["started"])).days >= 7


def today_n(week: dict, today: date) -> int:
    started = date.fromisoformat(week["started"])
    return max(1, min(7, (today - started).days + 1))


def toggle(week: dict, n: int, side: str) -> dict:
    done = {k: list(v) for k, v in week.get("done", {}).items()}
    marks = done.setdefault(str(n), [])
    marks.remove(side) if side in marks else marks.append(side)
    return {**week, "done": done}


def state(week: dict, today: date, side: str, open_all: bool) -> dict:
    """The week as this partner sees it: today's step, who marked what, which days are locked."""
    other = "b" if side == "a" else "a"
    n = today_n(week, today)
    days = []
    for d in week["days"]:
        marks = week.get("done", {}).get(str(d["n"]), [])
        locked = not open_all and d["n"] > FREE_DAYS
        days.append({**d, "mine": side in marks, "partner": other in marks, "both": side in marks and other in marks,
                     "locked": locked, "future": d["n"] > n})  # fmt: skip
        if locked:  # the title is the teaser; what to do that day is the paid part and never leaves the server
            days[-1] |= {"text": "", "steps": []}
    return {"days": days, "today": n, "done": sum(d["both"] for d in days), "started": week["started"], "finished": finished(week, today)}


if __name__ == "__main__":
    fake = {
        "QUESTION:money:": [{"question": "Q1", "depth": 1}, {"question": "Q1b", "depth": 1}, {"question": "Q2", "depth": 2}],
        "EXERCISE:money:": [{"title": "E", "steps": ["s"], "minutes": 10}],
    }
    w = build(
        [("money", "Деньги", 40), ("home", "Дом", 50), ("talk", "Общение", 60)], "Догоняю — убегаю", lambda p: fake.get(p, []), "seed"
    )
    assert len(w) == 7 and w[0]["kind"] == "talk" and w[-1]["kind"] == "reflect" and w[0]["sphere"] == "money"
    week = {"days": w, "started": "2026-11-20"}
    st = state(toggle(toggle(week, 1, "a"), 1, "b"), date(2026, 11, 22), "a", open_all=False)
    assert st["today"] == 3 and st["days"][0]["both"] and st["days"][1]["locked"] and st["done"] == 1
    assert st["days"][1]["text"] == "" and st["days"][1]["steps"] == [] and st["days"][1]["title"]  # nothing paid in the page
    nxt = build([("money", "Деньги", 40), ("home", "Дом", 50), ("talk", "Общение", 60)], "", lambda p: fake.get(p, []), "seed", round_=1)
    assert nxt[0]["title"] != w[0]["title"]  # the next week asks the next question of the sphere
    assert not st["finished"] and state(week, date(2026, 11, 27), "a", open_all=False)["finished"]
    print("ok")
