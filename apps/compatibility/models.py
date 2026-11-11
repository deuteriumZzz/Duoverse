"""Persistence (ADR-0003, ADR-0007, ADR-0010).

An Owner starts anonymous on a device; signing in by email turns it into an account that several
devices share. A pair belongs to its creator; the partner joins it from their own account.
"""

import uuid

from django.db import models

from apps.core.fields import EncryptedJSONField


class Owner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = EncryptedJSONField(null=True, blank=True)  # encrypted at rest; only for sign-in codes and receipts
    email_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)  # keyed HMAC, for lookup
    email_verified_at = models.DateTimeField(null=True, blank=True)
    telegram_chat_id = EncryptedJSONField(null=True, blank=True)  # set when the person links the bot; notifications go there
    name = models.CharField(max_length=60, blank=True)  # how the cabinet and the partner see this person
    avatar = models.CharField(max_length=20, blank=True)  # a key of apps.web.avatars.AVATARS
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"owner {self.id}"

    @property
    def is_account(self) -> bool:
        return bool(self.email_hash) or self.identities.exists()


class Identity(models.Model):
    """A sign-in from Yandex ID, VK ID or Telegram. The provider's user id is stored only as a keyed hash."""

    provider = models.CharField(max_length=16)
    subject_hash = models.CharField(max_length=64)
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="identities")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "subject_hash"], name="identity_unique_subject")]

    def __str__(self) -> str:
        return f"{self.provider} identity"


class Device(models.Model):
    """One signed-in browser. The cookie holds the device id, so a device can be signed out remotely."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="devices")
    user_agent = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_seen_at"]

    def __str__(self) -> str:
        return f"device {self.id}"


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
    partner = models.ForeignKey(Owner, on_delete=models.SET_NULL, null=True, blank=True, related_name="partner_pairs")
    invite_code = models.CharField(max_length=6, unique=True, null=True, blank=True)  # shown as K7M-2QX
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


class DailyAnswer(models.Model):
    """One partner's answer to the question of the day. The other side sees it only once both have answered."""

    pair = models.ForeignKey(Pair, on_delete=models.CASCADE, related_name="answers")
    side = models.CharField(max_length=1)  # "a" — the creator, "b" — the joined partner
    day = models.DateField()
    question = models.TextField()
    text = EncryptedJSONField()  # the answer itself, encrypted like birth data
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["pair", "side", "day"], name="one_answer_per_side_per_day")]
        ordering = ["-day"]

    def __str__(self) -> str:
        return f"{self.pair_id} {self.side} {self.day}"


class Purchase(models.Model):
    """A paid unlock: «deep» opens one pair for both partners; «plus» opens every pair of the payer for 30 days."""

    class Status(models.TextChoices):
        PENDING = "pending"
        SUCCEEDED = "succeeded"
        CANCELED = "canceled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Owner, on_delete=models.SET_NULL, null=True, related_name="purchases")  # receipts outlive deletion
    pair = models.ForeignKey(Pair, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchases")
    kind = models.CharField(max_length=8)  # deep | plus
    amount = models.PositiveIntegerField()  # rubles
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider_id = models.CharField(max_length=64, unique=True, null=True, blank=True)  # YooKassa payment id
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)  # plus only

    def __str__(self) -> str:
        return f"{self.kind} {self.amount}₽ {self.status}"


class QuizAnswer(models.Model):
    """One partner's picks in the quiz of the week; results open once both have answered."""

    pair = models.ForeignKey(Pair, on_delete=models.CASCADE, related_name="quiz_answers")
    side = models.CharField(max_length=1)
    quiz_key = models.CharField(max_length=16)
    picks = models.JSONField()  # option index per question
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["pair", "side", "quiz_key"], name="one_quiz_answer_per_side")]

    def __str__(self) -> str:
        return f"{self.pair_id} {self.side} {self.quiz_key}"


class GeoPlace(models.Model):
    """GeoNames populated places (cities500, CC BY 4.0): a birthplace anywhere on Earth, loaded by `places_load`."""

    id = models.PositiveIntegerField(primary_key=True)  # geonameid
    name = models.CharField(max_length=200)  # Russian when GeoNames has it, otherwise the local name
    name_en = models.CharField(max_length=200)
    country = models.CharField(max_length=2)
    lat = models.FloatField()
    lon = models.FloatField()
    tz = models.CharField(max_length=40)
    population = models.PositiveIntegerField(default=0)
    key = models.CharField(max_length=200, db_index=True)  # places.search_key(name)
    key_en = models.CharField(max_length=200, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["lat", "lon"]), models.Index(fields=["-population"], name="geoplace_population")]

    def __str__(self) -> str:
        return f"{self.name} ({self.country})"
