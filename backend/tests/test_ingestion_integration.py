from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings
from app.services.advanced_analyzer import AdvancedAnalyzer


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not settings.GEMINI_ENABLED or not settings.GEMINI_API_KEY,
    reason="Gemini not configured (set GEMINI_ENABLED=true and GEMINI_API_KEY).",
)
def test_gemini_live_roundtrip(tmp_path: Path) -> None:
    """Calls the real Gemini API to ensure the integration works end-to-end.

    This test is skipped unless a Gemini API key is configured.
    """
    image_path = tmp_path / "gemini_live_test.jpg"
    Image.new("RGB", (96, 96), (220, 80, 60)).save(image_path, format="JPEG")

    analyzer = AdvancedAnalyzer()
    result = analyzer.analyze(
        "integration-live",
        [(image_path, "IntegrationZone", "datacenter")],
    )

    assert result.status in {"ok", "no_insights"}
    assert result.prompt_hash and len(result.prompt_hash) == 64
    assert result.duration_ms is not None
    assert result.model == analyzer.model
    assert result.provider == analyzer.PROVIDER

    if result.summary:
        loaded = json.loads(result.summary)
        assert "observations" in loaded
        assert isinstance(loaded["observations"], list)
