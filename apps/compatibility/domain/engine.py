"""Combines universes: weighted total with proportional redistribution and the universes' agreement index."""

from dataclasses import dataclass
from statistics import pstdev

from apps.core.domain.scoring import ScoreResult, clamp

DEFAULT_WEIGHTS = {"astrology": 35, "psychology": 35, "numerology": 15, "tarot": 15}
AGREEMENT_SPREAD = 25  # a 25-point standard deviation means the universes fully disagree


@dataclass(frozen=True)
class Combined:
    total: int
    weights: dict[str, int]  # redistributed, sums to 100 over present universes
    agreement: int


def combine(results: dict[str, ScoreResult | None], weights: dict[str, int] | None = None) -> Combined:
    w = weights or DEFAULT_WEIGHTS
    present = {k: r for k, r in results.items() if r is not None and w.get(k, 0) > 0}
    if not present:
        raise ValueError("no universe could be scored")
    wsum = sum(w[k] for k in present)
    share = {k: (w[k] * 100 / wsum if k in present else 0) for k in results}
    rounded = {k: round(v) for k, v in share.items()}
    if present:  # keep the visible weights summing to exactly 100
        top = max(present, key=lambda k: share[k])
        rounded[top] += 100 - sum(rounded.values())
    total = sum(present[k].score * share[k] for k in present) / 100
    scores = [r.score for r in present.values()]
    agreement = 100 if len(scores) < 2 else clamp(100 - pstdev(scores) * 100 / AGREEMENT_SPREAD)
    return Combined(clamp(total), rounded, agreement)
