from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.pipelines.models import OCRResult, Observation, PipelineResult
from app.services.scoring import RiskScorer
from app.pipelines.ocr import extract_text
from app.pipelines.vision import detect_anomalies
from app.schemas.ingestion import FileMetadata


class IngestionPipeline:
    """Orchestrates OCR + vision inference to produce structured outputs."""

    def __init__(self, storage_root: Path, scorer: RiskScorer | None = None) -> None:
        self.storage_root = storage_root
        self.scorer = scorer or RiskScorer()

    def run(self, batch_id: str, files: Iterable[FileMetadata]) -> PipelineResult:
        observations: list[Observation] = []
        ocr_texts: list[OCRResult] = []

        for file_meta in files:
            path = Path(file_meta.stored_path)

            if file_meta.content_type.startswith("image/"):
                observations.extend(detect_anomalies(path))
                ocr_texts.append(OCRResult(source_file=file_meta.filename, text=extract_text(path)))
            elif file_meta.content_type == "application/pdf":
                ocr_texts.append(
                    OCRResult(
                        source_file=file_meta.filename,
                        text="[pdf-ingestion-pending]",
                    )
                )
            else:
                # Text files are stored directly as pseudo OCR output
                try:
                    ocr_texts.append(
                        OCRResult(source_file=file_meta.filename, text=path.read_text(encoding="utf-8"))
                    )
                except Exception:
                    ocr_texts.append(OCRResult(source_file=file_meta.filename, text=""))

        risk = self.scorer.score(batch_id, observations) if observations else None

        return PipelineResult(batch_id=batch_id, observations=observations, ocr_texts=ocr_texts, risk=risk)
