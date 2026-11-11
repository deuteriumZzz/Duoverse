"""YooKassa REST API: create a payment with a 54-ФЗ receipt and read its status.

Docs: https://yookassa.ru/developers/payment-acceptance/getting-started/quick-start ,
https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/payments
"""

import base64
import json
import urllib.request

from django.conf import settings

API = "https://api.yookassa.ru/v3/payments"


class PaymentError(Exception):
    pass


def enabled() -> bool:
    return bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)


def _request(url: str, payload: dict | None = None, idempotence_key: str = "") -> dict:
    token = base64.b64encode(f"{settings.YOOKASSA_SHOP_ID}:{settings.YOOKASSA_SECRET_KEY}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
    if idempotence_key:
        headers["Idempotence-Key"] = idempotence_key
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload else None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 — fixed https API host
            return json.loads(resp.read().decode())
    except (OSError, ValueError) as e:
        raise PaymentError(str(e)) from e


def create_payment(purchase_id: str, amount: int, description: str, email: str, return_url: str) -> tuple[str, str]:
    """Returns (payment id, confirmation url). The purchase id doubles as the idempotence key."""
    value = f"{amount}.00"
    data = _request(
        API,
        {
            "amount": {"value": value, "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": description[:128],
            "metadata": {"purchase_id": purchase_id},
            "receipt": {
                "customer": {"email": email},
                "items": [
                    {
                        "description": description[:128],
                        "quantity": 1.0,
                        "amount": {"value": value, "currency": "RUB"},
                        "vat_code": settings.YOOKASSA_VAT_CODE,
                        "payment_mode": "full_payment",
                        "payment_subject": "service",
                    }
                ],
            },
        },
        idempotence_key=purchase_id,
    )
    return data["id"], data["confirmation"]["confirmation_url"]


def payment_status(payment_id: str) -> str:
    """pending | waiting_for_capture | succeeded | canceled — always read from YooKassa, never from a notification body."""
    return _request(f"{API}/{payment_id}")["status"]
