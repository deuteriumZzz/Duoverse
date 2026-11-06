"""Claude adapter for the stitcher. Structured JSON output; refusals and API failures return None → block-only fallback."""

import logging
from typing import Any

import anthropic

log = logging.getLogger(__name__)
PRICE_PER_MTOK = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.1, 0.5)}


class AnthropicLLM:
    def __init__(self, api_key: str, model: str = "claude-opus-5-5", effort: str = "medium", timeout: float = 90.0):
        self.model, self.effort = model, effort
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)  # SDK retries 408/409/429/5xx itself

    def complete_json(self, system: str, user: str, schema: dict) -> str | None:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 16000,
            # thinking is always on for Opus 5.5 and sampling params (temperature) are rejected — effort is the control
            "output_config": {"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],  # stable rules → cached prefix
            "messages": [{"role": "user", "content": user}],
            "betas": ["server-side-fallback-2026-07-01"],
            "fallbacks": "default",  # on a safety decline the API re-runs on a fallback model in the same call
        }
        try:
            response = self.client.beta.messages.create(**params)
        except anthropic.APIConnectionError:
            log.warning("LLM unreachable — falling back to blocks")
            return None
        except anthropic.RateLimitError:
            log.warning("LLM rate limited after retries — falling back to blocks")
            return None
        except anthropic.APIStatusError as e:
            log.error("LLM error %s (request %s) — falling back to blocks", e.status_code, getattr(e, "request_id", None))
            return None
        u = response.usage
        cost_in, cost_out = PRICE_PER_MTOK.get(self.model, (0.0, 0.0))
        log.info(
            "stitch usage model=%s in=%s cache_read=%s out=%s cost=$%.4f request=%s",
            response.model,
            u.input_tokens,
            getattr(u, "cache_read_input_tokens", 0),
            u.output_tokens,
            (u.input_tokens * cost_in + u.output_tokens * cost_out) / 1e6,
            response._request_id,
        )
        if response.stop_reason == "refusal":
            log.warning("LLM refused (%s) — falling back to blocks", getattr(response.stop_details, "category", None))
            return None
        if response.stop_reason == "max_tokens":
            return None
        return next((b.text for b in response.content if b.type == "text"), None)
