"""Knowledge lookup by exact key. Only allowed statuses reach reports (prod: published only)."""

import string
from typing import Any

from django.conf import settings

from apps.knowledge.models import KnowledgeBlock


class _Keep(dict):
    """Unknown placeholders stay as written instead of breaking the report."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def fill(template: str, **fmt: Any) -> str:
    if not fmt:
        return template
    try:
        return string.Formatter().vformat(template, (), _Keep(fmt))
    except (ValueError, IndexError):  # stray braces in hand-written text
        return template


class KnowledgeRepository:
    def __init__(self, locale: str = "ru"):
        allowed = getattr(settings, "KB_ALLOWED_STATUSES", ["published"])
        rows = KnowledgeBlock.objects.filter(locale=locale, status__in=allowed).values("key", "text", "data")
        self._blocks = {r["key"]: r for r in rows}
        self.used: list[str] = []

    def text(self, key: str, default: str = "", **fmt: Any) -> str:
        block = self._blocks.get(key)
        if not block:
            return fill(default, **fmt)
        self.used.append(key)
        return fill(block["text"], **fmt)

    def data(self, key: str) -> dict:
        block = self._blocks.get(key)
        if block:
            self.used.append(key)
        return dict(block["data"]) if block else {}

    def series(self, prefix: str) -> list[dict]:
        """All blocks under `prefix` (e.g. «QUESTION:sex:»), in key order — for lists like questions or habits."""
        return [dict(self._blocks[k]["data"], key=k) for k in sorted(self._blocks) if k.startswith(prefix)]

    def has(self, key: str) -> bool:
        return key in self._blocks
