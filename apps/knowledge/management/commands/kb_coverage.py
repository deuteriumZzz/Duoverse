"""Which knowledge keys the report can ask for, and which are missing or not yet published."""

from django.core.management.base import BaseCommand

from apps.knowledge.catalog import expected_keys
from apps.knowledge.models import KnowledgeBlock


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
