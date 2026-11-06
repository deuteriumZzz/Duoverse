"""Demo couples for the example report and the dev scenario switcher. Only inputs live here — everything else is computed."""

from datetime import date, time

from apps.compatibility.application.build_report import PersonInput
from apps.compatibility.domain.report import Scenario
from apps.psychology.domain.instruments import ITEMS, LIKERT

SCENARIOS = [
    Scenario(key="ideal", title="Идеальная пара"),
    Scenario(key="complex", title="Сложная пара"),
    Scenario(key="no_time", title="Нет времени рождения"),
    Scenario(key="no_psych", title="Нет психоданных"),
    Scenario(key="dates_only", title="Только даты"),
    Scenario(key="error", title="Ошибка расчёта"),
]

# answer level 1..5 per scale (reverse-keyed items are mirrored automatically)
STYLES = {
    "anya": {
        "O": 5,
        "C": 3,
        "E": 4,
        "A": 5,
        "N": 3,
        "anx": 2,
        "avo": 1,
        "criticism": 2,
        "contempt": 1,
        "defensiveness": 2,
        "stonewalling": 1,
        "repair": 4,
    },
    "misha": {
        "O": 4,
        "C": 5,
        "E": 2,
        "A": 4,
        "N": 2,
        "anx": 1,
        "avo": 2,
        "criticism": 1,
        "contempt": 1,
        "defensiveness": 2,
        "stonewalling": 3,
        "repair": 4,
    },
    "lena": {
        "O": 4,
        "C": 3,
        "E": 4,
        "A": 4,
        "N": 4,
        "anx": 4,
        "avo": 2,
        "criticism": 4,
        "contempt": 3,
        "defensiveness": 4,
        "stonewalling": 2,
        "repair": 2,
    },
    "artem": {
        "O": 2,
        "C": 4,
        "E": 3,
        "A": 2,
        "N": 3,
        "anx": 2,
        "avo": 4,
        "criticism": 3,
        "contempt": 3,
        "defensiveness": 4,
        "stonewalling": 4,
        "repair": 2,
    },
}


def answers_for(style: str) -> dict[str, int]:
    levels = STYLES[style]
    return {i: (LIKERT + 1 - levels[it.scale] if it.reverse else levels[it.scale]) for i, it in ITEMS.items()}


def demo_pair(scenario: str) -> tuple[PersonInput, PersonInput]:
    anya = PersonInput("demo-anya", "Аня", date(1996, 3, 14), time(7, 40), "Санкт-Петербург", answers_for("anya"))
    misha = PersonInput("demo-misha", "Миша", date(1994, 9, 2), time(23, 15), "Казань", answers_for("misha"))
    if scenario == "complex":
        return (
            PersonInput("demo-lena", "Лена", date(1993, 7, 21), time(14, 5), "Москва", answers_for("lena")),
            PersonInput("demo-artem", "Артём", date(1991, 1, 8), time(5, 30), "Екатеринбург", answers_for("artem")),
        )
    if scenario == "no_time":
        return anya, PersonInput(misha.id, misha.name, misha.birth_date, None, misha.birth_place, misha.answers)
    if scenario == "no_psych":
        return PersonInput(anya.id, anya.name, anya.birth_date, anya.birth_time, anya.birth_place), PersonInput(
            misha.id, misha.name, misha.birth_date, misha.birth_time, misha.birth_place
        )
    if scenario == "dates_only":
        return PersonInput(anya.id, anya.name, anya.birth_date), PersonInput(misha.id, misha.name, misha.birth_date)
    return anya, misha
