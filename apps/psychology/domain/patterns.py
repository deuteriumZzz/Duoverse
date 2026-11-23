"""Recognisable scenarios across scales: features of one partner, of both, or of each in turn that together describe how
a pair tends to act. Texts live in the knowledge base as PSY:pattern:<key> and cite published research."""

from collections.abc import Callable
from dataclasses import dataclass

from .scoring import PsychProfile

_ORDER = {"low": 0, "mid": 1, "high": 2}


def level(value: float) -> str:
    """0–100 → low / mid / high; three bands are as fine as four-item scales honestly allow."""
    return "low" if value < 35 else "mid" if value < 65 else "high"


class F:
    """One partner's features in the terms the rules use."""

    def __init__(self, p: PsychProfile):
        self.p = p

    def t(self, trait: str) -> str:
        return level(self.p.ocean[trait])

    @property
    def att(self) -> str:
        return {"Тревожный": "anxious", "Избегающий": "avoidant", "Тревожно-избегающий": "fearful"}.get(self.p.attachment, "secure")

    def h(self, horseman: str, at_least: str = "high") -> bool:
        return _ORDER[self.p.horsemen[horseman]] >= _ORDER[at_least]

    @property
    def calm_conflict(self) -> bool:
        return not any(self.h(x, "mid") for x in self.p.horsemen)

    @property
    def rep(self) -> str:
        return level(self.p.repair)


@dataclass(frozen=True)
class Pattern:
    key: str
    sphere: str  # where it shows in «Разбор»
    tone: str  # synergy | attention | risk
    kind: str  # one: a feature of X · two: X has one feature, Y another · both: the pair together
    test: Callable[[F, F], bool]


R, A, S = "risk", "attention", "synergy"
PATTERNS: list[Pattern] = [
    # one partner
    Pattern("anxious_radar", "emotions", A, "one", lambda x, _: x.t("N") == "high" and x.att == "anxious"),
    Pattern("stress_criticism", "conflicts", A, "one", lambda x, _: x.t("N") == "high" and x.h("criticism", "mid")),
    Pattern("blunt_critic", "conflicts", A, "one", lambda x, _: x.t("A") == "low" and x.h("criticism")),
    Pattern("avoid_shutdown", "conflicts", A, "one", lambda x, _: x.att in ("avoidant", "fearful") and x.h("stonewalling")),
    Pattern("quiet_distance", "emotions", A, "one", lambda x, _: x.t("E") == "low" and x.att == "avoidant"),
    Pattern("order_critic", "home", A, "one", lambda x, _: x.t("C") == "high" and x.h("criticism", "mid")),
    Pattern("ideas_no_followthrough", "plans", A, "one", lambda x, _: x.t("O") == "high" and x.t("C") == "low"),
    Pattern("pleaser", "power", A, "one", lambda x, _: x.t("A") == "high" and x.att == "anxious"),
    Pattern("calm_distant", "emotions", A, "one", lambda x, _: x.t("N") == "low" and x.att == "avoidant"),
    Pattern("push_pull", "shadows", A, "one", lambda x, _: x.att == "fearful" and x.t("N") == "high"),
    Pattern("contempt_flood", "conflicts", R, "one", lambda x, _: x.h("contempt", "mid") and x.t("N") == "high"),
    Pattern("secure_anchor", "conflicts", S, "one", lambda x, _: x.att == "secure" and x.rep == "high"),
    # each in turn: X with one feature, Y with another
    Pattern("pursue_withdraw", "conflicts", R, "two", lambda x, y: x.att == "anxious" and y.att == "avoidant"),
    Pattern("critic_wall", "conflicts", R, "two", lambda x, y: x.h("criticism") and y.h("stonewalling")),
    Pattern("contempt_defense", "conflicts", R, "two", lambda x, y: x.h("contempt", "mid") and y.h("defensiveness", "mid")),
    Pattern("stabilizer", "emotions", S, "two", lambda x, y: x.t("N") == "high" and y.t("N") == "low"),
    Pattern("social_gap", "people", A, "two", lambda x, y: x.t("E") == "high" and y.t("E") == "low"),
    Pattern("manager_improviser", "home", A, "two", lambda x, y: x.t("C") == "high" and y.t("C") == "low"),
    Pattern("adventure_comfort", "attraction", A, "two", lambda x, y: x.t("O") == "high" and y.t("O") == "low"),
    Pattern("yield_imbalance", "power", A, "two", lambda x, y: x.t("A") == "high" and y.t("A") == "low"),
    Pattern("safe_base_anxious", "trust", S, "two", lambda x, y: x.att == "secure" and y.att == "anxious"),
    Pattern("safe_base_avoidant", "trust", S, "two", lambda x, y: x.att == "secure" and y.att == "avoidant"),
    Pattern("repair_initiator", "conflicts", S, "two", lambda x, y: x.rep == "high" and y.rep == "low"),
    Pattern("silence_alarm", "conflicts", A, "two", lambda x, y: x.att == "anxious" and y.h("stonewalling", "mid")),
    Pattern("critique_retreat", "conflicts", A, "two", lambda x, y: x.h("criticism", "mid") and y.att == "avoidant"),
    Pattern("sensitive_target", "talk", A, "two", lambda x, y: x.t("N") == "high" and y.h("criticism")),
    Pattern("explorer_worrier", "growth", A, "two", lambda x, y: x.t("O") == "high" and y.t("N") == "high"),
    # the pair together
    Pattern("strong_repair", "conflicts", S, "both", lambda a, b: a.rep == b.rep == "high" and a.calm_conflict and b.calm_conflict),
    Pattern("no_repair", "conflicts", R, "both", lambda a, b: a.rep == b.rep == "low"),
    Pattern("cold_war", "conflicts", A, "both", lambda a, b: a.h("stonewalling", "mid") and b.h("stonewalling", "mid")),
    Pattern("mutual_critique", "conflicts", A, "both", lambda a, b: a.h("criticism", "mid") and b.h("criticism", "mid")),
    Pattern("conflict_avoiders", "talk", A, "both", lambda a, b: a.t("A") == b.t("A") == "high" and not a.h("criticism", "mid") and not b.h("criticism", "mid")),
    Pattern("closed_world", "people", A, "both", lambda a, b: a.t("E") == b.t("E") == "low"),
    Pattern("chaos_fun", "plans", A, "both", lambda a, b: a.t("O") == b.t("O") == "high" and a.t("C") == b.t("C") == "low"),
    Pattern("money_loose", "money", A, "both", lambda a, b: a.t("C") == b.t("C") == "low"),
    Pattern("flooding", "conflicts", R, "both", lambda a, b: a.t("N") == b.t("N") == "high" and any(p.h(h) for p in (a, b) for h in p.p.horsemen)),
    Pattern("secure_pair", "trust", S, "both", lambda a, b: a.att == b.att == "secure"),
    Pattern("slow_talk", "talk", A, "both", lambda a, b: a.att == b.att == "avoidant"),
]  # fmt: skip
TONE_RANK = {R: 0, A: 1, S: 2}


def match(a: PsychProfile, b: PsychProfile) -> list[tuple[Pattern, str]]:
    """Every scenario that fits the pair, as (pattern, side of X); risks first, then things to watch, then strengths."""
    fa, fb = F(a), F(b)
    found: list[tuple[Pattern, str]] = []
    for p in PATTERNS:
        if p.kind == "both":
            if p.test(fa, fb):
                found.append((p, "a"))
            continue
        for side, x, y in (("a", fa, fb), ("b", fb, fa)):
            if p.test(x, y):
                found.append((p, side))
    return sorted(found, key=lambda m: TONE_RANK[m[0].tone])
