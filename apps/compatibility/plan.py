"""Weekly micro-habit plan: which habits the pair took on and on which days they did them.

Stored as plain JSON on the pair (demo report: in the session). Habits are keyed by title, so a
regenerated report keeps the check-ins of habits that are still in it.
"""

from datetime import date, timedelta

MAX_PICK = 3  # more than three at once and nothing sticks


def pick(plan: dict, titles: list[str], allowed: list[str], today: date) -> dict:
    picked = [t for t in dict.fromkeys(titles) if t in allowed][:MAX_PICK]
    return {**plan, "picked": picked, "started": plan.get("started") or today.isoformat()}


def toggle(plan: dict, title: str, today: date) -> dict:
    if title not in plan.get("picked", []):
        return plan
    done = {k: list(v) for k, v in plan.get("done", {}).items()}
    day = done.setdefault(today.isoformat(), [])
    day.remove(title) if title in day else day.append(title)
    if not day:
        del done[today.isoformat()]
    return {**plan, "done": done}


def state(plan: dict, today: date) -> dict:
    done = plan.get("done", {})
    monday = today - timedelta(days=today.weekday())
    week = [(monday + timedelta(days=i)).isoformat() for i in range(7)]
    picked = plan.get("picked", [])
    day = today if done.get(today.isoformat()) else today - timedelta(days=1)  # today not done yet doesn't break the streak
    streak = 0
    while done.get(day.isoformat()):
        streak, day = streak + 1, day - timedelta(days=1)
    return {
        "picked": picked,
        "habits": [
            {"title": t, "today": t in done.get(today.isoformat(), []), "week": [t in done.get(d, []) for d in week]} for t in picked
        ],
        "week": [bool(done.get(d)) for d in week],
        "today": today.weekday(),
        "streak": streak,
    }
