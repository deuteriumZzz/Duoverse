"""Data contract between the UI and any ReportProvider (see docs/contracts/report.md).

Fixtures in infrastructure/fixtures are validated against these models, so the real
backend only has to produce the same shape for the UI to keep working.
"""

from datetime import date, time
from typing import Literal

from pydantic import BaseModel

Layer = Literal["symbolic", "scientific"]
Tone = Literal["synergy", "neutral", "attention", "risk"]
Level = Literal["low", "mid", "high"]
UniverseKey = Literal["astrology", "numerology", "tarot", "psychology"]


class Partner(BaseModel):
    id: str
    name: str
    side: Literal["a", "b"]
    birth_date: date
    birth_time: time | None = None
    birth_place: str | None = None
    sun_sign: str
    has_psych: bool = True


class Evidence(BaseModel):
    """A traceable fact behind a statement — the 'why' the UI reveals."""

    source: str
    detail: str
    weight: float
    layer: Layer


class Category(BaseModel):
    key: str
    title: str
    icon: str
    score: int
    tone: Tone
    verdict: str
    evidence: list[Evidence]


class Universe(BaseModel):
    key: UniverseKey
    title: str
    icon: str
    layer: Layer
    score: int | None
    confidence: int
    weight: int
    verdict: str
    missing: str | None = None


class Insight(BaseModel):
    title: str
    text: str
    tone: Tone
    evidence: list[Evidence] = []


class PairType(BaseModel):
    """Role A × role B × dynamic (see domain/archetypes.py); the poster is generated from the two roles."""

    name: str
    role_a: str
    role_b: str
    dynamic: str
    why_a: list["Evidence"] = []
    why_b: list["Evidence"] = []
    icon: str
    tagline: str
    description: str
    traits: list[str]


class Accuracy(BaseModel):
    value: int
    missing: list[str] = []


class Risk(BaseModel):
    title: str
    likelihood: Level
    impact: Level
    note: str
    mitigation: str


class Aspect(BaseModel):
    planet_a: str
    symbol: str
    aspect: str
    planet_b: str
    orb: float
    tone: Tone
    meaning: str
    key: str = ""
    major: bool = True
    double: bool = False
    spheres: list[str] = []
    text: str = ""


class PlanetPos(BaseModel):
    name: str
    lon: float  # ecliptic longitude, 0–360°
    glyph: str = ""
    sign: str = ""
    degree: str = ""
    house: int | None = None
    retro: bool = False
    dignity: str | None = None
    text: str = ""


class Overlay(BaseModel):
    planet: str
    owner: Literal["a", "b"]
    house: int
    tone: Tone
    text: str


class CompositePos(BaseModel):
    point: str
    sign: str
    house: int | None = None
    text: str


class ChartBalance(BaseModel):
    elements: dict[str, int]
    modalities: dict[str, int]


class AstrologySection(BaseModel):
    houses_available: bool
    planets_a: list[PlanetPos] = []
    planets_b: list[PlanetPos] = []
    houses_a: list[float] = []  # cusps for the bi-wheel
    all_aspects: list[Aspect] = []
    overlays: list[Overlay] = []
    composite: list[CompositePos] = []
    composite_aspects: list[str] = []
    balance_a: ChartBalance | None = None
    balance_b: ChartBalance | None = None
    summary: str
    aspects: list[Aspect]
    insights: list[Insight]


class OceanTrait(BaseModel):
    key: str
    title: str
    a: int
    b: int
    note: str


class GottmanItem(BaseModel):
    key: str
    title: str
    level: Level
    note: str


class PsychologySection(BaseModel):
    available: bool
    ocean: list[OceanTrait] = []
    attachment_a: str | None = None
    attachment_b: str | None = None
    attachment_note: str | None = None
    gottman: list[GottmanItem] = []
    repair_index: int | None = None
    mbti_a: str | None = None
    mbti_b: str | None = None
    insights: list[Insight] = []


class NumberPair(BaseModel):
    title: str
    a: int
    b: int
    tone: Tone
    meaning: str


class MatrixPoint(BaseModel):
    title: str
    a: int
    b: int


class NumerologySection(BaseModel):
    numbers: list[NumberPair]
    pair_number: int
    pair_meaning: str
    matrix: list[MatrixPoint]
    insights: list[Insight]


class Arcana(BaseModel):
    number: int
    name: str
    keyword: str
    portrait: str


class TarotSection(BaseModel):
    available: bool = True
    a: Arcana | None = None
    b: Arcana | None = None
    pair: Arcana | None = None
    link_type: str = ""
    link_tone: Tone = "neutral"
    reading: str = ""
    questions: list[str] = []
    how: list[str] = []


class Habit(BaseModel):
    title: str
    cadence: str
    duration: str
    why: str
    evidence: Evidence


class Daily(BaseModel):
    question: str
    habit: str
    streak: int
    week: list[bool]


class SphereFactor(BaseModel):
    """One concrete reason from any universe, written as a paragraph about this pair."""

    title: str
    text: str
    tone: Tone
    layer: Layer
    universe: UniverseKey
    tech: str | None = None  # the calculation behind it, in the layer's own terms («Венера △ Марс · трин, орб 1.2°»)
    ref: str | None = None  # anchor on the layer page that shows this factor


class Sphere(BaseModel):
    """One life area of the full story: what works, what is hard, why, what to do, what to ask."""

    key: str
    title: str
    icon: str
    score: int
    tone: Tone
    summary: str
    story: list[str]
    evidence: list[Evidence]
    actions: list[str]
    question: str
    factors: list[SphereFactor] = []
    script: str | None = None  # typical escalation for tense spheres
    exercise: str = ""
    adult: bool = False  # 18+ chapter


class Report(BaseModel):
    id: str
    scenario: str
    algorithm_version: str
    created_at: date
    partners: tuple[Partner, Partner]
    total_score: int
    agreement_index: int
    agreement_note: str
    summary: str
    pair_type: PairType
    accuracy: Accuracy
    universes: list[Universe]
    categories: list[Category]
    synergy: list[Insight]
    friction: list[Insight]
    risks: list[Risk]
    astrology: AstrologySection
    psychology: PsychologySection
    numerology: NumerologySection
    tarot: TarotSection
    habits: list[Habit]
    daily: Daily
    spheres: list[Sphere] = []
    depth: dict[str, bool] = {}  # which inputs the report is built from: dates, time_place_a/b, psych
    kb_keys: list[str] = []  # knowledge blocks the text was built from (traceability)


class QuickCategory(BaseModel):
    title: str
    icon: str
    score: int
    tone: Tone


class QuickResult(BaseModel):
    """Instant mini-report from two birth dates only."""

    score: int
    pair_type: str
    role_a: str
    role_b: str
    dynamic: str
    why_a: list[str]
    why_b: list[str]
    pair_tagline: str
    sign_a: str
    sign_b: str
    categories: list[QuickCategory]
    arcana_a: Arcana
    arcana_b: Arcana
    arcana_pair: Arcana


class ReportSummary(BaseModel):
    id: str
    names: str
    created_at: date
    total_score: int
    pair_type: str
    mode: str


class GenerationStep(BaseModel):
    title: str
    detail: str
    icon: str


class Scenario(BaseModel):
    key: str
    title: str


class ReportUnavailable(Exception):
    """Calculation failed — the UI shows the error state."""
