"""Telegram Bot API: send a message; the webhook view handles /start <code> to link a chat to an account."""

import json
import logging
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)


def call(method: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 — fixed https API host
        return json.loads(resp.read().decode())


def send_message(chat_id: int | str, text: str, url: str = "") -> bool:
    if not settings.TELEGRAM_BOT_TOKEN:
        return False
    payload: dict = {"chat_id": chat_id, "text": text}
    if url.startswith("https://"):  # Telegram accepts only public https links in buttons
        payload["reply_markup"] = {"inline_keyboard": [[{"text": "Открыть Duoverse", "url": url}]]}
    elif url:
        payload["text"] = f"{text}\n{url}"
    try:
        return bool(call("sendMessage", payload).get("ok"))
    except (OSError, ValueError):
        log.warning("telegram send failed")
        return False
