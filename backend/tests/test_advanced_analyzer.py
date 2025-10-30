from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import patch
from app.services.advanced_analyzer import AdvancedAnalyzer, GeminiAnalysisResult, build_gemini_summary, gemini_to_observations
from app.pipelines.models import Observation
def _fake_gemini_response() -> str:
    return json.dumps(
        {
            "security_level": "critical",
            "perimeter_score": 3,
            "access_control_score": 4,
            "fire_safety_score": 5,
            "structural_score": 6,
            "vulnerabilities": [
                {
                    "category": "perimeter",
                    "type": "fence_breach",
                    "description": "Clôture affaissée",
                    "severity": "critical",
                    "location": "Côté gauche",
                    "recommendation": "Réparer immédiatement et ajouter barbelés.",
                }
            ],
            "security_assets": [],
            "immediate_risks": ["Intrusion possible"]
        }
    )
def test_gemini_to_observations_maps_vulnerabilities(tmp_path: Path) -> None:
    image_path = tmp_path / "scene.jpg"
    image_path.write_bytes(b"fake")
    result = json.loads(_fake_gemini_response())
    observations = gemini_to_observations(result, image_path, zone_name="perimeter_north")
    assert len(observations) == 2  # vuln + security_level alert
    vuln_obs = observations[0]
    assert vuln_obs.label == "security_fence_breach"
    assert vuln_obs.severity == "critical"
    assert vuln_obs.extra["category"] == "access_control"
    assert vuln_obs.extra["recommendation"]
    level_obs = observations[1]
    assert level_obs.label == "security_level_alert"
    assert level_obs.severity == "critical"
    assert level_obs.extra["security_level"] == "critical"
def test_advanced_analyzer_disabled(tmp_path: Path) -> None:
    analyzer = AdvancedAnalyzer()
    with patch.object(analyzer, "enabled", False):
        result = analyzer.analyze("batch-x", [(tmp_path, None, None)])
    assert isinstance(result, GeminiAnalysisResult)
    assert result.status == "disabled"
@patch("app.services.advanced_analyzer.AdvancedAnalyzer._call_gemini", return_value=_fake_gemini_response())
def test_advanced_analyzer_generates_summary(mock_call, tmp_path: Path) -> None:
    analyzer = AdvancedAnalyzer()
    with patch.object(analyzer, "enabled", True), patch.object(analyzer, "api_key", "dummy-key"):
        result = analyzer.analyze(
            "batch-x",
            [(tmp_path / "scene.jpg", "main_gate", "datacenter")],
        )
    assert result.status == "ok"
    assert result.observations
    assert result.summary is not None
    payload = json.loads(result.summary)
    assert payload["observations"]
def test_build_gemini_summary_handles_empty() -> None:
    assert build_gemini_summary([], []) is None
    summary = build_gemini_summary([Observation("file", "security_level_alert", 0.9, "high")], ["warn"])
    assert summary is not None