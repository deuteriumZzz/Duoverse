"""Scoring for the scientific layer: person profiles and pair score. Every coefficient is listed in docs/methodology/psychology.md."""

from dataclasses import dataclass
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

    @property
    def attachment(self) -> str:
        anx, avo = self.anxiety >= 3, self.avoidance >= 3
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

    styles = {a.attachment.split(",")[0], b.attachment.split(",")[0]}
    if a.secure and b.secure:
        add(12, {"emotions": 14, "conflict": 8}, "Привязанность", f"{a.attachment.lower()} · {b.attachment.lower()} — надёжная база")
    elif styles == {"Тревожный", "Избегающий"}:
        add(-15, {"emotions": -16, "conflict": -12}, "Привязанность", "тревожный · избегающий — риск цикла «догоняю — убегаю»")
    elif a.secure or b.secure:
        add(4, {"emotions": 5}, "Привязанность", f"{a.attachment.lower()} · {b.attachment.lower()} — надёжный партнёр стабилизирует")
    else:
        add(-6, {"emotions": -8, "conflict": -5}, "Привязанность", "оба стиля небезопасные — важно проговаривать потребности")

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
        levels = (a.horsemen[h], b.horsemen[h])
        weight = 2 if h == "contempt" else 1  # contempt is the strongest predictor in Gottman's work
        penalty = sum({"low": 0, "mid": 2, "high": 6}[lv] for lv in levels) * weight
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
