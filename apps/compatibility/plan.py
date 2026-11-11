"""Weekly micro-habit plan: which habits the pair took on and on which days they did them.

Stored as plain JSON on the pair (demo report: in the session). Habits are keyed by title, so a
regenerated report keeps the check-ins of habits that are still in it.
"""

from datetime import date, timedelta

MAX_PICK = 3  # more than three at once and nothing sticks


def pick(plan: dict, titles: list[str], allowed: list[str], today: date) -> dict:
    picked = [t for t in dict.fromkeys(titles) if t in allowed][:MAX_PICK]
    return {**plan, "picked": picked, "started": plan.get("started") or today.isoformat()}


def toggle(plan: dict, title: str, today: date, side: str = "a") -> dict:
    """Mark or unmark a habit for one partner today; marks are stored as "a:title" / "b:title"."""
    if title not in plan.get("picked", []):
        return plan
    done = {k: list(v) for k, v in plan.get("done", {}).items()}
    day = [f"a:{x}" if ":" not in x else x for x in done.setdefault(today.isoformat(), [])]  # unprefixed = before per-person marks
    mark = f"{side}:{title}"
    day.remove(mark) if mark in day else day.append(mark)
    done[today.isoformat()] = day
    if not day:
        del done[today.isoformat()]
    return {**plan, "done": done}


def _by(marks: list[str], side: str, title: str) -> bool:
    return f"{side}:{title}" in marks or (side == "a" and title in marks)


def state(plan: dict, today: date, side: str = "a") -> dict:
    """The week as one partner sees it: their own marks, the partner's today, and the shared week and streak."""
    done = plan.get("done", {})
    other = "b" if side == "a" else "a"
    monday = today - timedelta(days=today.weekday())
    week = [(monday + timedelta(days=i)).isoformat() for i in range(7)]
    picked = plan.get("picked", [])
    day = today if done.get(today.isoformat()) else today - timedelta(days=1)  # today not done yet doesn't break the streak
    streak = 0
    while done.get(day.isoformat()):
        streak, day = streak + 1, day - timedelta(days=1)
    t0 = done.get(today.isoformat(), [])
    return {
        "picked": picked,
        "habits": [
            {
                "title": t,
                "today": _by(t0, side, t),
                "partner": _by(t0, other, t),
                "week": [_by(done.get(d, []), "a", t) or _by(done.get(d, []), "b", t) for d in week],
            }
            for t in picked
        ],
        "week": [bool(done.get(d)) for d in week],
        "today": today.weekday(),
        "streak": streak,
    }
