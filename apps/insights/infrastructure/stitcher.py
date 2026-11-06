from django.conf import settings
from django.core.cache import cache


def build_stitcher():
    """LLM stitching when a key is configured; otherwise None and the report is assembled from blocks only."""
    if not settings.ANTHROPIC_API_KEY:
        return None
    from apps.insights.application.stitch import Stitcher
    from apps.insights.infrastructure.anthropic_llm import AnthropicLLM

    return Stitcher(AnthropicLLM(settings.ANTHROPIC_API_KEY, settings.LLM_MODEL, settings.LLM_EFFORT), cache)
