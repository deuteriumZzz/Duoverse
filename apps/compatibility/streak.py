"""«Дней подряд вместе»: days in a row you both answered the question of the day. One missed day a week is forgiven
(a freeze, as Duolingo does it), so one busy evening doesn't erase a month. Today counts once you both answered; until
then the streak stands on yesterday — today isn't missed yet.
"""

from datetime import date, timedelta


def pair_streak(both: set[date], today: date) -> tuple[int, bool]:
    """both: days you both answered → (days in a row, whether this week's freeze is still unused).
    A freeze bridges a single missed day between answered ones, at most one per ISO week."""
    day = today if today in both else today - timedelta(days=1)
    days, used = 0, set()
    while True:
        week = day.isocalendar()[:2]
        if day in both:
            days += 1
        elif week not in used and day - timedelta(days=1) in both:
            used.add(week)
        else:
            break
        day -= timedelta(days=1)
    return days, today.isocalendar()[:2] not in used


if __name__ == "__main__":
    today = date(2026, 11, 26)  # a Thursday
    run = {today - timedelta(days=i) for i in range(1, 11)}
    assert pair_streak(run, today) == (10, True)  # today not answered yet: the streak stands on yesterday
    assert pair_streak(run | {today}, today) == (11, True)
    gap = run - {today - timedelta(days=2)}  # Tuesday missed
    assert pair_streak(gap, today) == (9, False)  # bridged by this week's freeze, which is now spent
    two = gap - {today - timedelta(days=3)}  # Monday too: two days in a row can't be bridged
    assert pair_streak(two, today) == (1, True)
    weeks = gap - {today - timedelta(days=9)}  # another miss, in the week before: its own freeze
    assert pair_streak(weeks, today) == (8, False)
    assert pair_streak(set(), today) == (0, True)
    print("ok")
