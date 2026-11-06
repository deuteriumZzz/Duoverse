"""Composition root: real implementations are wired here; templates and views stay untouched."""

from functools import cache

from apps.astrology.infrastructure.ephemeris import CityGeocoder, SwissEphemeris
from apps.compatibility.infrastructure.engine_report_provider import EngineReportProvider


def _knowledge():
    from apps.knowledge.infrastructure.repository import KnowledgeRepository

    return KnowledgeRepository()


def _stitcher():
    from apps.insights.infrastructure.stitcher import build_stitcher

    return build_stitcher()


@cache
def report_provider() -> EngineReportProvider:
    return EngineReportProvider(ephemeris=SwissEphemeris(), geocoder=CityGeocoder(), knowledge=_knowledge, stitcher=_stitcher)
