"""Knowledge base (prompt §4.2): short, reviewed interpretation blocks addressed by deterministic keys."""

from django.db import models


class KnowledgeBlock(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        REVIEWED = "reviewed", "Проверено"
        PUBLISHED = "published", "Опубликовано"

    class Domain(models.TextChoices):
        ASTROLOGY = "astrology"
        NUMEROLOGY = "numerology"
        TAROT = "tarot"
        PSYCHOLOGY = "psychology"
        PAIR = "pair"  # cross-layer: categories, spheres, roles

    key = models.CharField(max_length=160)
    locale = models.CharField(max_length=5, default="ru")
    domain = models.CharField(max_length=12, choices=Domain.choices)
    text = models.TextField(blank=True, default="")
    data = models.JSONField(default=dict, blank=True)  # structured blocks: title, mitigation, cadence…
    evidence_level = models.CharField(max_length=10, choices=[("scientific", "scientific"), ("symbolic", "symbolic")], default="symbolic")
    sources = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1)
    reviewed_by = models.CharField(max_length=120, blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["key", "locale"], name="kb_unique_key_locale")]
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.key} [{self.locale}] · {self.status}"
