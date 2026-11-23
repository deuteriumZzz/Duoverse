"""The scientific layer cites real, checked sources: every text names them, every name resolves, the report shows them."""

import json
from pathlib import Path

import pytest

from apps.knowledge.catalog import psychology_keys
from apps.psychology.sources import SOURCES
from config.container import report_provider

SEED = json.loads((Path(__file__).resolve().parent.parent / "apps/knowledge/seed/ru_psychology.json").read_text(encoding="utf-8"))


def test_every_psychology_text_cites_known_sources():
    by_key = {b["key"]: b for b in SEED}
    assert sorted(by_key) == sorted(psychology_keys())
    for key, block in by_key.items():
        cited = block["data"]["sources"]
        assert cited, f"{key} cites nothing"
        assert not set(cited) - set(SOURCES), f"{key}: unknown {set(cited) - set(SOURCES)}"
        assert block["status"] == "published" and block["evidence_level"] == "scientific"


def test_sources_have_a_full_reference_and_checked_links():
    for key, s in SOURCES.items():
        assert s.short and len(s.full) > 40, key
        assert not s.url or s.url.startswith(("https://doi.org/10.", "https://www.gottman.com/")), key


@pytest.mark.django_db
def test_report_shows_research_with_sources():
    p = report_provider().get_report("ideal").psychology
    assert p.available and p.bibliography and len(p.findings) == 8
    assert all(t.note and t.a_text and t.b_text and t.sources for t in p.ocean)
    assert p.attachment_a_text and p.attachment_sources and p.repair_note
    shorts = {c.short for c in p.bibliography}
    assert all(s in shorts for t in p.ocean for s in t.sources)  # what is cited inline is in the list
    spheres = report_provider().get_report("ideal").spheres
    assert all(s.science and s.science_sources for s in spheres)
