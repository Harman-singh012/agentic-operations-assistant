from django.conf import settings
from django.core.management.base import BaseCommand

from agent.vectorstore import ingest


class Command(BaseCommand):
    help = "Embed policy markdown files from ./policies into ChromaDB (idempotent)."

    def handle(self, *args, **opts):
        n = ingest(settings.POLICY_DIR)
        self.stdout.write(self.style.SUCCESS(f"Indexed {n} policy chunks."))
