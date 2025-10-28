from __future__ import annotations

import hashlib
from pathlib import Path

from app.pipelines.models import OCRResult, Observation, PipelineResult, RiskBreakdown, RiskScore
from app.services.report import ReportBuilder


def _dummy_pipeline_result(tmp_path: Path) -> PipelineResult:
    observations = [
        Observation(source_file="fire.jpg", label="incendie", confidence=0.92, severity="high"),
        Observation(source_file="door.jpg", label="malveillance", confidence=0.65, severity="medium"),
    ]
    ocr_entries = [
        OCRResult(source_file="fire.jpg", text="Extincteur absent dans la zone."),
        OCRResult(source_file="notes.txt", text="Vérifier l'accès badge."),
    ]
    risk = RiskScore(
        batch_id="batch-123",
        total_score=24.0,
        normalized_score=0.24,
        breakdown=[
            RiskBreakdown(label="incendie", severity="high", count=1, score=14.0),
            RiskBreakdown(label="malveillance", severity="medium", count=1, score=10.0),
        ],
    )
    return PipelineResult(batch_id="batch-123", observations=observations, ocr_texts=ocr_entries, risk=risk)


def test_report_builder_generates_pdf(tmp_path: Path) -> None:
    builder = ReportBuilder(output_dir=tmp_path)
    result = _dummy_pipeline_result(tmp_path)

    artifact = builder.build_from_pipeline(result)

    assert artifact.path.exists()
    assert artifact.path.suffix == ".pdf"
    size = artifact.path.stat().st_size
    assert size > 0

    hasher = hashlib.sha256()
    with artifact.path.open("rb") as pdf_file:
        while chunk := pdf_file.read(4096):
            hasher.update(chunk)
    assert artifact.checksum_sha256 == hasher.hexdigest()
