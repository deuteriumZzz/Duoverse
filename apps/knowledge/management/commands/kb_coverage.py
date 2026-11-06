"""Which knowledge keys the report can ask for, and which are missing or not yet published."""

from django.core.management.base import BaseCommand

from apps.compatibility.domain.archetypes import DYNAMICS, ROLES
from apps.knowledge.models import KnowledgeBlock

CATS = ["passion", "emotions", "communication", "values", "conflict", "home"]
TONES = ["synergy", "neutral", "attention", "risk"]
SPHERES = ["attraction", "emotions", "talk", "conflicts", "home", "money", "plans", "people", "growth"]


def expected_keys() -> list[str]:
    keys = [f"CAT:{c}:{t}" for c in CATS for t in TONES]
    keys += [f"INSIGHT:{c}:{k}" for c in CATS for k in ("good", "hard")]
    keys += [f"{p}:{c}" for p in ("RISK", "HABIT", "DAILY") for c in CATS]
    keys += [f"SPHERE:{s}" for s in SPHERES] + [f"ROLE:{r}" for r in ROLES] + [f"SUMMARY:{d}" for d in DYNAMICS]
    keys += [f"PAIRTYPE:{a}+{b}" for a in ROLES for b in ROLES if a <= b]
    return keys


class Command(BaseCommand):
    help = "Show knowledge base coverage for the report."

    def add_arguments(self, parser):
        parser.add_argument("--locale", default="ru")

    def handle(self, *args, locale="ru", **opts):
        have = dict(KnowledgeBlock.objects.filter(locale=locale).values_list("key", "status"))
        keys = expected_keys()
        missing = [k for k in keys if k not in have]
        drafts = [k for k in keys if have.get(k) == "draft"]
        self.stdout.write(f"expected {len(keys)} · present {len(keys) - len(missing)} · drafts {len(drafts)} · missing {len(missing)}")
        groups: dict[str, int] = {}
        for k in missing:
            groups[k.split(":")[0]] = groups.get(k.split(":")[0], 0) + 1
        for g, n in sorted(groups.items()):
            self.stdout.write(f"  missing {g}: {n}")
