"""Content pipeline: catalog, Claude drafting into drafts, daily question and habits from the knowledge base."""

import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from django.core.management import call_command

from apps.knowledge.catalog import expected_keys, groups
from apps.knowledge.infrastructure.repository import fill
from apps.knowledge.models import KnowledgeBlock

pytestmark = pytest.mark.django_db


def test_fill_keeps_unknown_placeholders_and_stray_braces():
    assert fill("{a} и {b_gen}", a="Аня") == "Аня и {b_gen}"
    assert fill("скобка { без пары", a="Аня") == "скобка { без пары"


def test_catalog_covers_every_sphere_and_aspect_direction():
    keys = set(expected_keys())
    assert "QUESTION:sex:28" in keys and "EXERCISE:shadows:03" in keys and "PAIRTYPE:compass+sail" in keys
    assert "ASPECT:Венера:trine:Марс" in keys and "ASPECT:Марс:trine:Венера" in keys and "OVERLAY:Луна:8" in keys
    assert len(keys) == len(expected_keys())  # no duplicates


class FakeBatches:
    def __init__(self, reply):
        self.reply, self.created = reply, None

    def create(self, requests):
        self.created = requests
        return SimpleNamespace(id="msgbatch_test")

    def retrieve(self, batch_id):
        return SimpleNamespace(processing_status="ended", request_counts=SimpleNamespace(processing=0))

    def results(self, batch_id):
        for r in self.created:
            items = self.reply(r["custom_id"], r["params"]["messages"][0]["content"])
            msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps({"items": items}))])
            yield SimpleNamespace(custom_id=r["custom_id"], result=SimpleNamespace(type="succeeded", message=msg))


def test_kb_draft_saves_only_valid_items_as_drafts(monkeypatch):
    from apps.knowledge.management.commands import kb_draft

    group = next(g for g in groups() if g.keys[0].startswith("PAIRTYPE:"))
    KnowledgeBlock.objects.filter(key=group.keys[0]).delete()

    def reply(custom_id, prompt):
        assert group.keys[0] in prompt
        return [
            {"key": group.keys[0], "text": "Пара держится на доверии и общем деле, а напряжение снимает юмор."},
            {"key": "PAIRTYPE:x+y", "text": "чужой ключ"},
        ]

    fake = SimpleNamespace(messages=SimpleNamespace(batches=FakeBatches(reply)))
    monkeypatch.setattr(kb_draft.Command, "client", lambda self: fake)
    call_command("kb_draft", only="PAIRTYPE", limit=1)
    block = KnowledgeBlock.objects.get(key=group.keys[0])
    assert block.status == "draft" and "доверии" in block.text
    assert not KnowledgeBlock.objects.filter(key="PAIRTYPE:x+y").exists()


def test_validation_rejects_predictions_and_unknown_placeholders():
    from apps.knowledge.management.commands.kb_draft import validate

    g = next(g for g in groups() if g.keys[0].startswith("ASPECT:"))
    ok, problems = validate(
        g,
        [
            {"key": g.keys[0], "text": "{a} и {b} легко находят общий язык и поддерживают друг друга."},
            {"key": g.keys[1], "text": "Вас ждёт измена и расставание в этом году, без вариантов."},
            {"key": g.keys[2], "text": "{owner} влияет на партнёра — это заметно в быту и в спорах."},
        ],
    )
    assert list(ok) == [g.keys[0]]
    assert any("forbidden" in p for p in problems) and any("placeholder" in p for p in problems)


def test_daily_question_changes_by_day_and_leans_on_weak_spheres():
    from apps.web.views import question_of_day
    from config.container import report_provider

    report = report_provider().get_report("hard")
    weak = {s.key for s in sorted(report.spheres, key=lambda s: s.score)[:4]}
    pools = {
        k: {b.data["question"] for b in KnowledgeBlock.objects.filter(key__startswith=f"QUESTION:{k}:")}
        for k in [s.key for s in report.spheres]
    }
    days = [date(2026, 11, 1) + timedelta(days=i) for i in range(14)]
    asked = [question_of_day(report, "pair-1", d) for d in days]
    assert len(set(asked)) >= 10  # a different question most days
    assert question_of_day(report, "pair-1", days[0]) == asked[0]  # both partners see the same one
    from_weak = sum(any(q in pools[k] for k in weak) for q in asked)
    assert from_weak >= 7  # every other day at least


def test_report_habits_come_from_the_weakest_spheres():
    from config.container import report_provider

    report = report_provider().get_report("hard")
    titles = set(KnowledgeBlock.objects.filter(key__startswith="HABIT:", key__regex=r":\d\d$").values_list("data__title", flat=True))
    assert report.habits and all(h.title in titles for h in report.habits)


def test_pair_type_description_comes_from_the_knowledge_base():
    from config.container import report_provider

    report = report_provider().get_report("ideal")
    keys = sorted([report.pair_type.role_a, report.pair_type.role_b])
    block = KnowledgeBlock.objects.get(key=f"PAIRTYPE:{keys[0]}+{keys[1]}")
    assert report.pair_type.description == block.text


def test_every_sphere_has_a_year_of_questions_and_three_exercises():
    from apps.knowledge.catalog import SPHERES

    for sphere in SPHERES:
        assert KnowledgeBlock.objects.filter(key__startswith=f"QUESTION:{sphere}:", status="published").count() == 28
        assert KnowledgeBlock.objects.filter(key__startswith=f"EXERCISE:{sphere}:", status="published").count() == 3


def test_knowledge_base_is_complete_and_reports_have_no_raw_placeholders():
    import re

    from apps.knowledge.catalog import expected_keys
    from config.container import report_provider

    have = set(KnowledgeBlock.objects.values_list("key", flat=True))
    assert not [k for k in expected_keys() if k not in have]
    for scenario in ("ideal", "hard", "no_time"):
        blob = report_provider().get_report(scenario).model_dump_json()
        assert not re.findall(r"\{[a-z_]+\}", blob), scenario


def test_reverse_aspect_swaps_the_people():
    import re

    def swap(t: str) -> str:
        return re.sub(r"\{(a|b)((?:_\w+)?)\}", lambda m: "{" + ("b" if m.group(1) == "a" else "a") + m.group(2) + "}", t)

    fwd = KnowledgeBlock.objects.get(key="ASPECT:Солнце:square:Луна").text
    back = KnowledgeBlock.objects.get(key="ASPECT:Луна:square:Солнце").text
    assert "{a" in fwd and back == swap(fwd) and back != fwd
