"""Slice A: deterministic calculations — numerology, arcana layer, weighting engine."""

from datetime import date

import pytest

from apps.compatibility.domain.engine import combine
from apps.core.domain.scoring import ScoreResult
from apps.numerology.domain import numerology as num
from apps.tarot.domain import tarot


@pytest.mark.parametrize(
    ("d", "expected"),
    [(date(1996, 3, 14), 33), (date(1994, 9, 2), 7), (date(1993, 7, 21), 5), (date(1991, 1, 8), 11), (date(2000, 1, 1), 4)],
)
def test_life_path_keeps_master_numbers(d, expected):
    assert num.life_path(d) == expected


def test_destiny_uses_pythagorean_cyrillic_table():
    assert num.destiny("Аня") == 4  # А1 + Н6 + Я6 = 13 → 4
    assert num.destiny("Anna") == num.reduce(1 + 5 + 5 + 1)
    assert num.destiny("—") is None


def test_master_numbers_fold_for_comparison():
    assert num.base(33) == 6 and num.base(11) == 2 and num.base(22) == 4


def test_matrix_points_stay_within_22_arcana():
    for d in [date(1999, 12, 29), date(1900, 1, 1), date(2026, 11, 6)]:
        assert all(1 <= v <= 22 for v in num.destiny_matrix(d).values())


@pytest.mark.parametrize(("d", "arcana"), [(date(1996, 3, 14), 11), (date(1994, 9, 2), 12), (date(1993, 7, 21), 10), (date(1991, 1, 8), 7)])
def test_arcana_from_birth_date(d, arcana):
    assert tarot.arcana_of(d) == arcana


def test_pair_arcana_and_link():
    assert tarot.pair_arcana(11, 12) == 1
    assert tarot.link(11, 12).type == "Дополняющие"  # Маг is a uniting arcana
    assert tarot.link(7, 7).type == "Зеркальные"
    assert tarot.how("Ани", date(1996, 3, 14), "Миши", date(1994, 9, 2))[2].endswith("Маг")


def test_engine_redistributes_missing_universes():
    c = combine({"astrology": ScoreResult(80, 90), "psychology": None, "numerology": ScoreResult(70, 90), "tarot": ScoreResult(90, 90)})
    assert c.weights == {"astrology": 54, "psychology": 0, "numerology": 23, "tarot": 23}
    assert sum(c.weights.values()) == 100


def test_engine_agreement_drops_when_universes_disagree():
    close = combine({"astrology": ScoreResult(80, 90), "psychology": ScoreResult(82, 90)})
    apart = combine({"astrology": ScoreResult(85, 90), "psychology": ScoreResult(40, 90)})
    assert close.agreement > 90 > 30 > apart.agreement


def test_engine_requires_at_least_one_universe():
    with pytest.raises(ValueError):
        combine({"astrology": None})


def test_scores_are_deterministic():
    pa, pb = num.profile(date(1996, 3, 14), "Аня", date(2026, 1, 1)), num.profile(date(1994, 9, 2), "Миша", date(2026, 1, 1))
    assert num.score(pa, pb) == num.score(pa, pb)


def test_first_names_decline_and_unknown_shapes_stay():
    from apps.core.domain.names import dat, gen

    assert [gen(n) for n in ("Аня", "Миша", "Ольга", "Иван", "Андрей", "Мария")] == ["Ани", "Миши", "Ольги", "Ивана", "Андрея", "Марии"]
    assert [dat(n) for n in ("Аня", "Миша", "Иван", "Мария")] == ["Ане", "Мише", "Ивану", "Марии"]
    assert gen("Alex") == "Alex" and gen("Анри") == "Анри"
