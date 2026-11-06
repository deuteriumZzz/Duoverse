"""Persistence (ADR-0003, ADR-0007). No user accounts: data belongs to an anonymous device Owner."""

import uuid

from django.db import models

from apps.core.fields import EncryptedJSONField


class Owner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = EncryptedJSONField(null=True, blank=True)  # optional, only for moving to another device and receipts
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"owner {self.id}"


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="people")
    name = models.CharField(max_length=80)
    birth = EncryptedJSONField()  # {"date": "1996-03-14", "time": "07:40" | null, "place": "Казань" | null}
    answers = EncryptedJSONField(null=True, blank=True)  # questionnaire item → 1..5
    answered_at = models.DateTimeField(null=True, blank=True)
    consent_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return self.name


class Pair(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="pairs")
    a = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="+")
    b = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="+")
    mode = models.CharField(max_length=12, default="extended")
    plan = models.JSONField(default=dict, blank=True)  # weekly micro-habits, see compatibility/plan.py
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"pair {self.id}"


class StoredReport(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        READY = "ready"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pair = models.ForeignKey(Pair, on_delete=models.CASCADE, related_name="reports")
    input_hash = models.CharField(max_length=64)
    algorithm_version = models.CharField(max_length=16)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    snapshot = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["input_hash", "algorithm_version"])]

    def __str__(self) -> str:
        return f"report {self.id} · {self.status}"
