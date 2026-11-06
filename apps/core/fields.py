"""Encrypted model fields for personal data (birth data, questionnaire answers, email)."""

import base64
import hashlib
import json
from functools import cache
from typing import Any

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


@cache
def _fernet() -> Fernet:
    key = (
        getattr(settings, "FIELD_ENCRYPTION_KEY", "")
        or base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()).decode()
    )
    return Fernet(key.encode())


class EncryptedJSONField(models.Field):  # type: ignore[type-arg]  # runtime Field is not generic
    """JSON value stored as a Fernet token. Not queryable by design — personal data is only ever loaded by owner."""

    def get_internal_type(self) -> str:
        return "TextField"

    def from_db_value(self, value: str | None, expression: Any, connection: Any) -> Any:
        return None if value is None else json.loads(_fernet().decrypt(value.encode()))

    def to_python(self, value: Any) -> Any:
        return value

    def get_prep_value(self, value: Any) -> str | None:
        return None if value is None else _fernet().encrypt(json.dumps(value, ensure_ascii=False).encode()).decode()
