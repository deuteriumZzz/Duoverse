"""Knowledge lookup by exact key. Only allowed statuses reach reports (prod: published only)."""

from typing import Any

from django.conf import settings

from apps.knowledge.models import KnowledgeBlock


class KnowledgeRepository:
    def __init__(self, locale: str = "ru"):
        allowed = getattr(settings, "KB_ALLOWED_STATUSES", ["published"])
        rows = KnowledgeBlock.objects.filter(locale=locale, status__in=allowed).values("key", "text", "data")
        self._blocks = {r["key"]: r for r in rows}
        self.used: list[str] = []

    def text(self, key: str, default: str = "", **fmt: Any) -> str:
        block = self._blocks.get(key)
        if not block:
            return default.format(**fmt) if fmt else default
        self.used.append(key)
        return block["text"].format(**fmt) if fmt else block["text"]

    def data(self, key: str) -> dict:
        block = self._blocks.get(key)
        if block:
            self.used.append(key)
        return dict(block["data"]) if block else {}

    def has(self, key: str) -> bool:
        return key in self._blocks
