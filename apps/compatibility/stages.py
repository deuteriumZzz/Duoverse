"""The pair's path in three stages, so nothing arrives before its time (Aron et al., 1997: closeness grows when openness
rises step by step, not all at once). The stage comes from days you both answered the question of the day — not from
the calendar — and decides how deep questions go, which spheres are asked about, which quizzes come, and what
«Сегодня» shows.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    n: int  # 1, 2, 3
    title: str
    text: str
    depth: int  # the deepest question level asked at this stage
    starts: int  # days answered together when it opens


STAGES = (
    Stage(1, "Знакомство заново", "Лёгкие вопросы и то, что у вас уже получается.", 1, 0),
    Stage(2, "Глубже", "Вопросы глубже, и понемногу — о том, где вам непросто.", 2, 10),
    Stage(3, "Откровенно", "Самые личные разговоры — вы уже в ритме.", 3, 25),
)
SENSITIVE = {"sex", "shadows", "conflicts"}  # not at stage one: first get used to talking at all
OPENS = {"week": (3, 7), "talk": (5, 10), "quiz": (5, 10)}  # tile: (days answered together, or days since you paired)


# what each stage opens, for «Ваш путь» — so the pair always knows what comes next: (glyph, text)
ROADMAP = {
    1: (
        ("message-circle", "Вопрос дня — лёгкие вопросы о том, что у вас уже получается"),
        ("sprout", "Привычки из разбора — каждый понедельник две новые"),
        ("heart", "Свидание недели — идея на выходные"),
        ("zap", "«Неделя пары» — через 3 дня вместе"),
        ("gem", "«Как мы?» и квиз недели — через 5 дней вместе, сначала лёгкие темы"),
        ("sprout", "Дерево: каждый общий ответ — новый листок"),
    ),
    2: (
        ("message-circle", "Вопросы глубже — и понемногу о том, где вам непросто"),
        ("gem", "Квизы о деньгах, быте, семье и доверии"),
        ("star", "Тема недели — там, где в квизе вы ответили по-разному"),
        ("sprout", "На стволе дерева — ленточка: вы стали ближе"),
    ),
    3: (
        ("message-circle", "Самые личные разговоры"),
        ("gem", "Квизы «Ревность и границы» и «Близость и нежность»"),
        ("flame", "Откровенные вопросы о близости — только если оба включили «Близость 18+»"),
        ("sprout", "На коре — вырезанное сердце"),
    ),
}


def roadmap(days_together: int) -> list[dict]:
    """The whole path for «Ваш путь»: each stage with its state (done, now, ahead) and what it opens."""
    now = stage_for(days_together)
    return [{"stage": s, "state": "done" if s.n < now.n else "now" if s.n == now.n else "ahead", "items": ROADMAP[s.n]} for s in STAGES]


def stage_for(days_together: int) -> Stage:
    return [s for s in STAGES if days_together >= s.starts][-1]


def next_stage(days_together: int) -> tuple[Stage, int] | None:
    """The stage ahead and how many more days together it takes; None at the last one."""
    nxt = next((s for s in STAGES if s.starts > days_together), None)
    return (nxt, nxt.starts - days_together) if nxt else None


def question_ok(sphere: str, depth: int, stage: Stage, intimate: bool) -> bool:
    """Whether a question of `sphere` at `depth` may be asked now. Sex: never at stage one, only light at stage two,
    and its deepest questions only once both of you switched «Близость 18+» on."""
    if depth > stage.depth:
        return False
    if sphere in SENSITIVE and stage.n == 1:
        return False
    if sphere == "sex":
        return depth <= (1 if stage.n == 2 else 3 if intimate else 2)
    return True


def opened(days_together: int, days_paired: int) -> set[str]:
    """Tiles of «Сегодня» that are open: the question and habits from day one, the week of the pair after a few days
    together, the weekly talk and quiz a little later — or after enough calendar days, so nobody waits forever."""
    later = {k for k, (together, paired) in OPENS.items() if days_together >= together or days_paired >= paired}
    return {"question", "habits", "date"} | later


if __name__ == "__main__":
    assert stage_for(0).n == 1 and stage_for(9).n == 1 and stage_for(10).n == 2 and stage_for(40).n == 3
    assert next_stage(4) == (STAGES[1], 6) and next_stage(30) is None
    s1, s2, s3 = STAGES
    assert question_ok("home", 1, s1, False) and not question_ok("home", 2, s1, False)
    assert not question_ok("sex", 1, s1, True) and not question_ok("conflicts", 1, s1, False)  # nothing sensitive at first
    assert question_ok("sex", 1, s2, False) and not question_ok("sex", 2, s2, True)
    assert not question_ok("sex", 3, s3, False) and question_ok("sex", 3, s3, True)  # the deepest only with «Близость» on
    assert opened(0, 0) == {"question", "habits", "date"} and "week" in opened(3, 0) and "quiz" in opened(0, 10)
    assert [r["state"] for r in roadmap(12)] == ["done", "now", "ahead"] and all(r["items"] for r in roadmap(0))
    print("ok")
