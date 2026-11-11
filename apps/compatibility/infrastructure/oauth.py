"""Sign-in through Yandex ID, VK ID (OAuth 2.1 with PKCE) and the Telegram Login Widget.

Endpoints and parameters follow the providers' docs:
- Yandex ID: https://yandex.ru/dev/id/doc/ru/codes/code-url, https://yandex.ru/dev/id/doc/ru/user-information
- VK ID: https://id.vk.ru/about/business/go/docs/ru/vkid/latest/vk-id/connection/api-description
- Telegram: https://core.telegram.org/widgets/login#checking-authorization
A provider is offered only when its keys are set in the environment.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class ProviderUser:
    provider: str
    subject: str  # the provider's stable user id
    email: str | None  # only when the provider shares an address
    email_verified: bool = False


class OAuthError(Exception):
    pass


def enabled() -> list[str]:
    out = []
    if settings.YANDEX_CLIENT_ID and settings.YANDEX_CLIENT_SECRET:
        out.append("yandex")
    if settings.VK_CLIENT_ID:
        out.append("vk")
    if settings.TELEGRAM_BOT_NAME and settings.TELEGRAM_BOT_TOKEN:
        out.append("telegram")
    return out


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]  # 43–128 chars of [A-Za-z0-9_-]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorize_url(provider: str, redirect_uri: str, state: str, challenge: str) -> str:
    common = {
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if provider == "yandex":
        return "https://oauth.yandex.ru/authorize?" + urllib.parse.urlencode({**common, "client_id": settings.YANDEX_CLIENT_ID})
    if provider == "vk":
        return "https://id.vk.ru/authorize?" + urllib.parse.urlencode({**common, "client_id": settings.VK_CLIENT_ID, "scope": "email"})
    raise OAuthError(provider)


def _request(url: str, data: dict | None = None, headers: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"Accept": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 — fixed https provider URLs
            payload = json.loads(resp.read().decode())
    except (OSError, ValueError) as e:
        raise OAuthError(str(e)) from e
    if "error" in payload:
        raise OAuthError(payload.get("error_description") or payload["error"])
    return payload


def exchange(provider: str, params: dict, redirect_uri: str, verifier: str, state: str) -> ProviderUser:
    """Code → token → user, from the query string the provider sent back."""
    code = params.get("code") or ""
    if not code:
        raise OAuthError(params.get("error_description") or params.get("error") or "no code")
    if provider == "yandex":
        token = _request(
            "https://oauth.yandex.ru/token",
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.YANDEX_CLIENT_ID,
                "client_secret": settings.YANDEX_CLIENT_SECRET,
                "code_verifier": verifier,
            },
        )
        info = _request("https://login.yandex.ru/info?format=json", headers={"Authorization": f"OAuth {token['access_token']}"})
        return ProviderUser("yandex", str(info["id"]), info.get("default_email"), email_verified=bool(info.get("default_email")))
    if provider == "vk":
        body = {
            "grant_type": "authorization_code",
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "code": code,
            "client_id": settings.VK_CLIENT_ID,
            "device_id": params.get("device_id", ""),
            "state": state,
        }
        if settings.VK_SERVICE_TOKEN:  # confidential apps only
            body["service_token"] = settings.VK_SERVICE_TOKEN
        token = _request("https://id.vk.ru/oauth2/auth", body)
        user = _request("https://id.vk.ru/oauth2/user_info", {"client_id": settings.VK_CLIENT_ID, "access_token": token["access_token"]})[
            "user"
        ]
        return ProviderUser("vk", str(user["user_id"]), user.get("email") or None)
    raise OAuthError(provider)


TELEGRAM_MAX_AGE = 24 * 3600


def telegram_user(params: dict) -> ProviderUser:
    """Check the Login Widget signature: HMAC-SHA256 over the sorted fields, keyed with SHA256(bot token)."""
    received = params.get("hash", "")
    fields = {k: v for k, v in params.items() if k != "hash"}
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode()).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(expected, received):
        raise OAuthError("bad telegram signature")
    if time.time() - int(fields.get("auth_date", "0")) > TELEGRAM_MAX_AGE:
        raise OAuthError("telegram login expired")
    return ProviderUser("telegram", str(fields["id"]), None)
