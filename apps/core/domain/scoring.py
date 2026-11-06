"""Shared scoring vocabulary: every universe returns a ScoreResult made of traceable factors."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

Layer = Literal["symbolic", "scientific"]


@dataclass(frozen=True)
class Factor:
    source: str
    detail: str
    weight: float
    layer: Layer
    category: str | None = None  # passion | emotions | communication | values | conflict | home


@dataclass(frozen=True)
class ScoreResult:
    score: int  # 0–100
    confidence: int  # 0–100: how complete the inputs were
    factors: list[Factor] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=dict)  # passion, emotions, communication, values, conflict, home


class CompatibilityScorer(Protocol):
    key: str

    def score(self, a: object, b: object) -> ScoreResult | None: ...


def clamp(x: float, lo: int = 0, hi: int = 100) -> int:
    return int(max(lo, min(hi, round(x))))
