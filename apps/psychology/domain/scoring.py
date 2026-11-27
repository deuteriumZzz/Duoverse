"""Scoring for the scientific layer: person profiles and pair score. Every coefficient is listed in docs/methodology/psychology.md."""

from dataclasses import dataclass, field
from statistics import mean

from apps.core.domain.scoring import Factor, ScoreResult, clamp

from .instruments import ITEMS, LIKERT

TRAITS = {
    "O": "Открытость опыту",
    "C": "Добросовестность",
    "E": "Экстраверсия",
    "A": "Доброжелательность",
    "N": "Эмоциональная чувствительность",
}
HORSEMEN = {"criticism": "Критика", "contempt": "Презрение", "defensiveness": "Оборона", "stonewalling": "Уход в себя"}


class IncompleteAnswers(ValueError):
    pass


@dataclass(frozen=True)
class PsychProfile:
    ocean: dict[str, int]  # 0–100
    anxiety: float  # 1–5
    avoidance: float
    horsemen: dict[str, str]  # low | mid | high
    repair: int  # 0–100
    horsemen_mean: dict[str, float] = field(default_factory=dict)  # 1–5, what the score reads (the levels are for words)

    @property
    def attachment(self) -> str:
        # anxious / avoidant only above the middle of the scale: «3 — иногда» is the middle, not a lean
        anx, avo = self.anxiety > 3, self.avoidance > 3
        if anx and avo:
            return "Тревожно-избегающий"
        if anx:
            return "Тревожный"
        if avo:
            return "Избегающий"
        return "Надёжный, с тревожными нотками" if self.anxiety >= 2.6 else "Надёжный"

    @property
    def secure(self) -> bool:
        return self.attachment.startswith("Надёжный")


def _value(item_id: str, raw: int) -> int:
    if not 1 <= raw <= LIKERT:
        raise IncompleteAnswers(f"{item_id}: {raw} вне шкалы 1–{LIKERT}")
    return LIKERT + 1 - raw if ITEMS[item_id].reverse else raw


def _scale(answers: dict[str, int], scale: str) -> float:
    vals = [_value(i, answers[i]) for i, item in ITEMS.items() if item.scale == scale and i in answers]
    if not vals:
        raise IncompleteAnswers(scale)
    return mean(vals)


def _pct(m: float) -> int:
    return clamp((m - 1) / (LIKERT - 1) * 100)


def _level(m: float) -> str:
    return "low" if m < 2.5 else "mid" if m < 3.5 else "high"


def profile(answers: dict[str, int]) -> PsychProfile:
    return PsychProfile(
        ocean={t: _pct(_scale(answers, t)) for t in TRAITS},
        anxiety=round(_scale(answers, "anx"), 2),
        avoidance=round(_scale(answers, "avo"), 2),
        horsemen={h: _level(_scale(answers, h)) for h in HORSEMEN},
        repair=_pct(_scale(answers, "repair")),
        horsemen_mean={h: round(_scale(answers, h), 2) for h in HORSEMEN},
    )


def score(a: PsychProfile, b: PsychProfile) -> ScoreResult:
    f: list[Factor] = []
    total = 70.0
    cats = dict.fromkeys(["passion", "emotions", "communication", "values", "conflict", "home"], 65.0)

    def add(delta: float, cat_deltas: dict[str, float], source: str, detail: str) -> None:
        nonlocal total
        total += delta
        for c, d in cat_deltas.items():
            cats[c] += d
        main = max(cat_deltas, key=lambda c: abs(cat_deltas[c])) if cat_deltas else None
        f.append(Factor(source, detail, round(delta / 15, 2), "scientific", main))

    # Attachment moves the score by how far the two of you are from the middle of the scales: both low on anxiety and
    # avoidance (+2) gives what «надёжная база» used to, both high (−2) what the worst pairing did, the middle nothing —
    # so answering «иногда» throughout no longer reads as a problem. The pursue–withdraw pairing keeps its own weight.
    styles = {a.attachment.split(",")[0], b.attachment.split(",")[0]}
    sec = sum(3 - x for p in (a, b) for x in (p.anxiety, p.avoidance)) / 4  # −2 … +2
    why = (
        "надёжная база"
        if a.secure and b.secure
        else "надёжный партнёр стабилизирует"
        if a.secure or b.secure
        else "важно проговаривать потребности"
    )
    add(sec * 6, {"emotions": sec * 7, "conflict": sec * 4}, "Привязанность", f"{a.attachment.lower()} · {b.attachment.lower()} — {why}")
    if styles == {"Тревожный", "Избегающий"}:
        add(-6, {"emotions": -8, "conflict": -6}, "Привязанность", "тревожный · избегающий — риск цикла «догоняю — убегаю»")

    n = (a.ocean["N"] + b.ocean["N"]) / 2
    add(
        -(n - 50) * 0.25,
        {"emotions": -(n - 50) * 0.3, "conflict": -(n - 50) * 0.2},
        "Эмоциональная чувствительность",
        f"{a.ocean['N']} и {b.ocean['N']} из 100",
    )
    ag = (a.ocean["A"] + b.ocean["A"]) / 2
    add(
        (ag - 50) * 0.2,
        {"values": (ag - 50) * 0.3, "conflict": (ag - 50) * 0.2},
        "Доброжелательность",
        f"{a.ocean['A']} и {b.ocean['A']} из 100",
    )
    gap_e = abs(a.ocean["E"] - b.ocean["E"])
    add(
        -max(0, gap_e - 25) * 0.15,
        {"communication": -max(0, gap_e - 25) * 0.4},
        "Экстраверсия",
        f"{a.ocean['E']} и {b.ocean['E']} — разрыв {gap_e}",
    )
    gap_c = abs(a.ocean["C"] - b.ocean["C"])
    add(
        -max(0, gap_c - 25) * 0.1,
        {"home": -max(0, gap_c - 25) * 0.4},
        "Добросовестность",
        f"{a.ocean['C']} и {b.ocean['C']} — разрыв {gap_c}",
    )
    o = (a.ocean["O"] + b.ocean["O"]) / 2
    cats["passion"] += (o - 50) * 0.2

    for h, title in HORSEMEN.items():
        weight = 2 if h == "contempt" else 1  # contempt is the strongest predictor in Gottman's work
        # only what lies above the middle costs: «иногда» (3) nothing, 4.5 what «высокий» used to (6), 5 a bit more (8)
        penalty = round(sum(max(0.0, p.horsemen_mean.get(h, 3.0) - 3) * 4 for p in (a, b)) * weight, 2)
        if penalty:
            add(
                -penalty,
                {"conflict": -penalty * 1.4, "communication": -penalty * 0.6},
                title,
                f"уровень: {a.horsemen[h]} · {b.horsemen[h]}".replace("low", "низкий").replace("mid", "средний").replace("high", "высокий"),
            )
    rep = (a.repair + b.repair) / 2
    add((rep - 50) * 0.2, {"conflict": (rep - 50) * 0.3}, "Индекс восстановления", f"{round(rep)} из 100")

    return ScoreResult(clamp(total, 20, 96), 88, f, {k: clamp(v, 20, 95) for k, v in cats.items()})
