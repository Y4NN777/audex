from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings
from app.pipelines.models import OCRResult, Observation, RiskBreakdown, RiskScore
from app.services.report_summary import ReportSummaryService, SummaryRequest


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not settings.GEMINI_SUMMARY_ENABLED or not (settings.GEMINI_SUMMARY_API_KEY or settings.GEMINI_API_KEY),
    reason="Gemini summary is not configured (enable GEMINI_SUMMARY_ENABLED and set an API key).",
)
def test_report_summary_live_call(tmp_path: Path) -> None:
    """Calls Gemini summary endpoint to validate integration in real conditions."""
    # Create a temporary image to simulate context in OCR/observations (not strictly required but nice for prompt)
    image_path = tmp_path / "summary-context.jpg"
    Image.new("RGB", (96, 96), (220, 90, 60)).save(image_path, format="JPEG")

    risk = RiskScore(
        batch_id="integration-summary",
        total_score=18.0,
        normalized_score=0.18,
        breakdown=[RiskBreakdown(label="incendie", severity="high", count=2, score=12.0)],
    )
    observations_local = [
        Observation(source_file=image_path.name, label="incendie", confidence=0.93, severity="high"),
    ]
    # Pretend Gemini already raised some findings (optional)
    observations_gemini = [
        Observation(source_file=image_path.name, label="security_missing_fire_equipment", confidence=0.8, severity="high"),
    ]
    ocr_entries = [
        OCRResult(source_file="journal.txt", text="Extincteur manquant près de l'entrée principale."),
    ]

    request = SummaryRequest(
        batch_id="integration-summary",
        risk=risk,
        observations_local=observations_local,
        observations_gemini=observations_gemini,
        ocr_texts=ocr_entries,
    )

    service = ReportSummaryService()
    result = service.generate(request)

    assert result.status in {"ok", "no_content"}
    assert result.source in {"google-gemini", "none"}  # fallback to disabled in edge cases
    # Basic sanity checks when summary returns content
    if result.status == "ok":
        assert result.text is not None and len(result.text) > 0
        assert result.prompt_hash is not None
        assert result.response_hash is not None
