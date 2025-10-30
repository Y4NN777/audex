from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.pipelines.models import OCRResult, Observation, RiskBreakdown, RiskScore
from app.services.report_summary import ReportSummaryService, SummaryRequest


def _make_request() -> SummaryRequest:
    risk = RiskScore(
        batch_id="batch-1",
        total_score=12.5,
        normalized_score=0.125,
        breakdown=[RiskBreakdown(label="incendie", severity="high", count=2, score=8.0)],
    )
    observations = [
        Observation(source_file="photo.jpg", label="incendie", confidence=0.92, severity="high"),
    ]
    ocr = [
        OCRResult(source_file="note.txt", text="Extincteur manquant près de la sortie."),
    ]
    return SummaryRequest(
        batch_id="batch-1",
        risk=risk,
        observations_local=observations,
        observations_gemini=[],
        ocr_texts=ocr,
    )


def test_report_summary_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GEMINI_SUMMARY_ENABLED", False, raising=False)
    service = ReportSummaryService()
    result = service.generate(_make_request())
    assert result.status == "disabled"
    assert result.text is None
    assert result.findings == []
    assert result.recommendations == []
    assert result.source == "none"


def test_report_summary_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GEMINI_SUMMARY_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "GEMINI_SUMMARY_REQUIRED", False, raising=False)
    monkeypatch.setattr(settings, "GEMINI_SUMMARY_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(settings, "GEMINI_SUMMARY_MODEL", "test-model", raising=False)
    monkeypatch.setattr(settings, "GEMINI_SUMMARY_TIMEOUT_SECONDS", 15, raising=False)
    monkeypatch.setattr(settings, "GEMINI_SUMMARY_MAX_RETRIES", 0, raising=False)

    service = ReportSummaryService()

    payload = json.dumps(
        {
            "summary": "Site globalement conforme.",
            "key_findings": ["Extincteur absent zone A"],
            "recommendations": ["Installer un extincteur à la zone A"],
            "warnings": [],
        }
    )
    monkeypatch.setattr(service, "_call_gemini", lambda prompt: (payload, 987))

    result = service.generate(_make_request())
    assert result.status == "ok"
    assert result.text == "Site globalement conforme."
    assert result.findings == ["Extincteur absent zone A"]
    assert result.recommendations == ["Installer un extincteur à la zone A"]
    assert result.warnings == []
    assert result.duration_ms == 987
    assert result.prompt_hash is not None and len(result.prompt_hash) == 64
    assert result.response_hash is not None and len(result.response_hash) == 64


def test_report_summary_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GEMINI_SUMMARY_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "GEMINI_SUMMARY_REQUIRED", False, raising=False)
    monkeypatch.setattr(settings, "GEMINI_SUMMARY_API_KEY", "fallback-key", raising=False)
    monkeypatch.setattr(settings, "SUMMARY_FALLBACK_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "SUMMARY_FALLBACK_MODEL", "fallback-model", raising=False)

    service = ReportSummaryService()
    monkeypatch.setattr(service, "_call_gemini", side_effect=RuntimeError("network-error"))

    result = service.generate(_make_request())
    assert result.status == "fallback"
    assert result.source == "fallback-model"
    assert result.text is not None
    assert "Analyse avancée indisponible" in result.text
