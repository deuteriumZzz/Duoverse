"""LLM stitching (prompt §4): the model only rewrites the summary and sphere stories from the blocks and facts we give it."""

import hashlib
import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from apps.compatibility.domain.report import Report
from apps.core.domain.names import forms
from apps.insights.domain.validator import PLANETS, check_paragraph

log = logging.getLogger(__name__)
PROMPT_VERSION = "stitch_v2"
SYSTEM = (Path(__file__).resolve().parent.parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")
MAX_ATTEMPTS = 3  # first try + 2 retries with the validator's feedback

PARAGRAPH = {
    "type": "object",
    "properties": {"text": {"type": "string"}, "block_ids": {"type": "array", "items": {"type": "string"}}},
    "required": ["text", "block_ids"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {
        "summary": PARAGRAPH,
        "spheres": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"key": {"type": "string"}, "paragraphs": {"type": "array", "items": PARAGRAPH}},
                "required": ["key", "paragraphs"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "spheres"],
    "additionalProperties": False,
}


class LLM(Protocol):
    model: str

    def complete_json(self, system: str, user: str, schema: dict) -> str | None: ...


class Cache(Protocol):
    def get(self, key: str) -> object: ...

    def set(self, key: str, value: object, timeout: int | None = None) -> None: ...


def masks(report: Report) -> list[tuple[str, str]]:
    """(name form, token) pairs, longest first: names never leave our servers (152-ФЗ, no cross-border transfer).
    The model writes {a_gen}, {b_dat}… and `apply` puts the real forms back."""
    pairs = [(form, "{" + who + case + "}") for who, p in zip("ab", report.partners, strict=True) for case, form in forms(p.name).items()]
    return sorted(pairs, key=lambda m: -len(m[0]))


def _mask(text: str, pairs: list[tuple[str, str]]) -> str:
    for form, token in pairs:
        text = re.sub(rf"(?<!\w){re.escape(form)}(?!\w)", token, text)
    return text


def _unmask(text: str, pairs: list[tuple[str, str]]) -> str:
    for form, token in pairs:
        text = text.replace(token, form)
    return text


def facts_of(report: Report) -> dict:
    """The closed context: facts + blocks with ids, names replaced by tokens. Nothing else reaches the model."""
    blocks = {"summary": report.summary, **{f"sphere:{s.key}:{i}": p for s in report.spheres for i, p in enumerate(s.story)}}
    blocks |= {f"insight:{i.title}": i.text for i in report.synergy + report.friction}
    blocks |= {f"evidence:{e.source}": f"{e.source} — {e.detail}" for s in report.spheres for e in s.evidence}
    facts = {
        "names": ["{a}", "{b}"],
        "pair_type": {"name": report.pair_type.name, "tagline": report.pair_type.tagline, "dynamic": report.pair_type.dynamic},
        "total_score": report.total_score,
        "categories": [{"title": c.title, "score": c.score, "tone": c.tone} for c in report.categories],
        "spheres": [
            {
                "key": s.key,
                "title": s.title,
                "score": s.score,
                "tone": s.tone,
                "block_ids": [f"sphere:{s.key}:{i}" for i in range(len(s.story))] + [f"evidence:{e.source}" for e in s.evidence],
            }
            for s in report.spheres
        ],
        "blocks": [{"id": k, "text": v} for k, v in blocks.items()],
    }
    return json.loads(_mask(json.dumps(facts, ensure_ascii=False), masks(report)))


def _allowed(facts: dict) -> tuple[set[str], set[str], set[str]]:
    ids = {blk["id"] for blk in facts["blocks"]}
    corpus = json.dumps(facts, ensure_ascii=False)
    numbers = {n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", corpus)}
    planets = {p for p in PLANETS if p[:-1] in corpus}
    return ids, numbers, planets


def validate(payload: dict, facts: dict) -> list[str]:
    ids, numbers, planets = _allowed(facts)
    errors = [f"summary: {e}" for e in check_paragraph(payload["summary"]["text"], payload["summary"]["block_ids"], ids, numbers, planets)]
    keys = {s["key"] for s in facts["spheres"]}
    tokens = {"{" + w + c + "}" for w in "ab" for c in ("", "_gen", "_dat", "_acc", "_ins", "_pre")}
    texts = [payload["summary"]["text"]] + [p["text"] for s in payload["spheres"] for p in s["paragraphs"]]
    errors += [f"неизвестная метка {t}" for t in sorted({t for x in texts for t in re.findall(r"\{[^{}]*\}", x)} - tokens)]
    for s in payload["spheres"]:
        if s["key"] not in keys:
            errors.append(f"неизвестная сфера {s['key']}")
        for p in s["paragraphs"]:
            errors += [f"{s['key']}: {e}" for e in check_paragraph(p["text"], p["block_ids"], ids, numbers, planets)]
    return errors


class Stitcher:
    def __init__(self, llm: LLM, cache: Cache, on_usage: Callable[[dict], None] | None = None):
        self.llm, self.cache, self.on_usage = llm, cache, on_usage

    def stitch(self, report: Report) -> Report:
        facts = facts_of(report)
        key = (
            "stitch:"
            + hashlib.sha256(json.dumps([facts, PROMPT_VERSION, self.llm.model], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        )
        payload = self.cache.get(key)
        if payload is None:
            payload = self._generate(facts)
            if payload is None:
                return report  # fallback: the report stays assembled from blocks only
            self.cache.set(key, payload, timeout=60 * 60 * 24 * 30)
        return apply(report, payload)  # type: ignore[arg-type]

    def _generate(self, facts: dict) -> dict | None:
        user = "Факты и блоки пары (JSON):\n" + json.dumps(facts, ensure_ascii=False)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            raw = self.llm.complete_json(SYSTEM, user, SCHEMA)
            if raw is None:
                return None  # API unavailable or refused — no point retrying the same input
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                errors = ["ответ не является JSON"]
            else:
                errors = validate(payload, facts)
                if not errors:
                    return payload
            log.warning("stitch attempt %s rejected: %s", attempt, errors[:5])
            user += "\n\nПредыдущий ответ отклонён проверкой. Исправь и ответь заново:\n- " + "\n- ".join(errors[:12])
        return None


def apply(report: Report, payload: dict) -> Report:
    m = masks(report)
    stories = {s["key"]: [_unmask(p["text"], m) for p in s["paragraphs"]] for s in payload["spheres"] if s["paragraphs"]}
    spheres = [s.model_copy(update={"story": stories.get(s.key, s.story)}) for s in report.spheres]
    return report.model_copy(update={"summary": _unmask(payload["summary"]["text"], m), "spheres": spheres})
