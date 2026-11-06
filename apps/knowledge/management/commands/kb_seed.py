from django.core.management.base import BaseCommand

from apps.knowledge.models import KnowledgeBlock
from apps.knowledge.seeding import load_seed


class Command(BaseCommand):
    help = "Load the bundled knowledge seed (keeps reviewed/published edits)."

    def handle(self, *args, **opts):
        self.stdout.write(f"{load_seed(KnowledgeBlock)} blocks loaded")
