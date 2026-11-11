"""Slice E: LLM stitching is validated by code and always has a block-only fallback. No network in tests."""

import json
from types import SimpleNamespace

import pytest
from django.core.cache import cache as django_cache

from apps.insights.application.stitch import Stitcher, facts_of, validate
from apps.insights.infrastructure.anthropic_llm import AnthropicLLM
from config.container import report_provider

pytestmark = pytest.mark.django_db


@pytest.fixture
def report():
    return report_provider().get_report("ideal")


def good_payload(r) -> dict:
    facts = facts_of(r)
    sphere = facts["spheres"][0]
    return {
        "summary": {"text": f"{r.partners[0].name} и {r.partners[1].name} — пара, где различия помогают.", "block_ids": ["summary"]},
        "spheres": [
            {
                "key": sphere["key"],
                "paragraphs": [
                    {"text": "Вам легко тянуться друг к другу, и это стоит беречь новизной.", "block_ids": [sphere["block_ids"][0]]}
                ],
            }
        ],
    }


class FakeLLM:
    model = "fake"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete_json(self, system, user, schema):
        self.calls.append(user)
        return self.replies.pop(0) if self.replies else None


def test_valid_output_replaces_summary_and_sphere_story(report):
    django_cache.clear()
    llm = FakeLLM([json.dumps(good_payload(report))])
    out = Stitcher(llm, django_cache).stitch(report)
    assert out.summary.endswith("различия помогают.") and out.spheres[0].story == [
        "Вам легко тянуться друг к другу, и это стоит беречь новизной."
    ]
    assert out.total_score == report.total_score  # numbers never come from the model


def test_validator_rejects_invented_facts_then_retry_succeeds(report):
    django_cache.clear()
    bad = good_payload(report)
    bad["summary"] = {"text": "Вам нельзя быть вместе: Хирон и 999 баллов.", "block_ids": ["made-up"]}
    errors = validate(bad, facts_of(report))
    assert (
        any("block_ids" in e for e in errors)
        and any("999" in e for e in errors)
        and any("запрещ" in e for e in errors)
        and any("Хирон" in e for e in errors)
    )
    llm = FakeLLM([json.dumps(bad), json.dumps(good_payload(report))])
    out = Stitcher(llm, django_cache).stitch(report)
    assert len(llm.calls) == 2 and "отклонён проверкой" in llm.calls[1]
    assert "нельзя" not in out.summary


def test_three_rejections_fall_back_to_blocks(report):
    django_cache.clear()
    bad = json.dumps({"summary": {"text": "без опоры", "block_ids": []}, "spheres": []})
    out = Stitcher(FakeLLM([bad, bad, bad]), django_cache).stitch(report)
    assert out == report


def test_unavailable_model_falls_back_and_cache_avoids_repeat_calls(report):
    django_cache.clear()
    assert Stitcher(FakeLLM([]), django_cache).stitch(report) == report
    llm = FakeLLM([json.dumps(good_payload(report))])
    Stitcher(llm, django_cache).stitch(report)
    again = FakeLLM([])
    assert Stitcher(again, django_cache).stitch(report).summary.endswith("различия помогают.") and again.calls == []


def test_adapter_treats_refusal_as_fallback(monkeypatch):
    llm = AnthropicLLM(api_key="test-key")
    usage = SimpleNamespace(input_tokens=10, output_tokens=0, cache_read_input_tokens=0)
    refusal = SimpleNamespace(
        stop_reason="refusal",
        stop_details=SimpleNamespace(category="cyber"),
        usage=usage,
        model="claude-opus-5-5",
        _request_id="req_1",
        content=[],
    )
    sent = {}
    monkeypatch.setattr(llm.client.beta.messages, "create", lambda **kw: sent.update(kw) or refusal)
    assert llm.complete_json("sys", "user", {"type": "object"}) is None
    assert sent["model"] == "claude-opus-5-5" and sent["fallbacks"] == "default" and "temperature" not in sent
    assert sent["output_config"]["format"]["type"] == "json_schema" and sent["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_names_never_reach_the_model_and_come_back_declined(report):
    from apps.core.domain.names import forms

    django_cache.clear()
    a, b = (p.name for p in report.partners)
    sent = json.dumps(facts_of(report), ensure_ascii=False)
    assert all(f not in sent for n in (a, b) for f in forms(n).values() if len(f) > 2)
    payload = good_payload(report)
    payload["summary"]["text"] = "{a_dat} и {b_dat} легко вместе, а с {b_ins} спокойно."
    llm = FakeLLM([json.dumps(payload)])
    out = Stitcher(llm, django_cache).stitch(report)
    assert out.summary == f"{forms(a)['_dat']} и {forms(b)['_dat']} легко вместе, а с {forms(b)['_ins']} спокойно."
    assert a not in llm.calls[0]


def test_unknown_token_is_rejected(report):
    payload = good_payload(report)
    payload["summary"]["text"] = "{c} и {a} — пара."
    assert any("{c}" in e for e in validate(payload, facts_of(report)))
