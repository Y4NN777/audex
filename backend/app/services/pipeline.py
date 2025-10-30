from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Iterable, List

from app.pipelines.models import OCRResult, Observation, PipelineResult
from app.services.scoring import RiskScorer
from app.services.ocr_engine import get_ocr_engine
from app.services.vision_engine import get_vision_engine
from app.schemas.ingestion import FileMetadata


class IngestionPipeline:
    """Orchestrates OCR + vision inference to produce structured outputs."""

    def __init__(self, storage_root: Path, scorer: RiskScorer | None = None) -> None:
        self.storage_root = storage_root
        self.scorer = scorer or RiskScorer()
        self._ocr_engine = get_ocr_engine()
        self._vision_engine = get_vision_engine()
        self._ocr_engine_name = getattr(self._ocr_engine, "engine_id", "unknown")

    def run(
        self,
        batch_id: str,
        files: Iterable[FileMetadata],
        progress: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> PipelineResult:
        file_list: List[FileMetadata] = list(files)
        observations: list[Observation] = []
        ocr_texts: list[OCRResult] = []

        total_files = len(file_list)

        if progress:
            progress(
                "analysis:start",
                {
                    "label": "Analyse OCR & vision démarrée",
                    "fileCount": total_files,
                    "progress": 25,
                },
            )

        for index, file_meta in enumerate(file_list, start=1):
            if progress:
                ratio = min(max(index / max(total_files, 1), 0.0), 1.0)
                vision_progress = 30 + int(15 * ratio)
                ocr_progress = 50 + int(15 * ratio)
                progress(
                    "vision:start",
                    {
                        "label": f"Analyse visuelle de {file_meta.filename}",
                        "file": file_meta.filename,
                        "position": index,
                        "total": total_files,
                        "progress": max(25, vision_progress - 5),
                    },
                )

            path = Path(file_meta.stored_path)
            is_image = file_meta.content_type.startswith("image/")

            if is_image:
                observations.extend(self._vision_engine.detect(path))
                if progress:
                    progress(
                        "vision:complete",
                        {
                            "label": f"Analyse visuelle terminée ({file_meta.filename})",
                            "file": file_meta.filename,
                            "position": index,
                            "total": total_files,
                            "progress": vision_progress,
                        },
                    )
            else:
                if progress:
                    progress(
                        "vision:complete",
                        {
                            "label": f"Aucune analyse visuelle requise ({file_meta.filename})",
                            "file": file_meta.filename,
                            "position": index,
                            "total": total_files,
                            "progress": vision_progress,
                        },
                    )

            if progress:
                progress(
                    "ocr:start",
                    {
                        "label": f"OCR en cours ({file_meta.filename})",
                        "file": file_meta.filename,
                        "position": index,
                        "total": total_files,
                        "progress": max(vision_progress, ocr_progress - 5),
                    },
                )

            ocr_result = self._ocr_engine.extract(file_meta)
            ocr_texts.append(ocr_result)

            if ocr_result.error and progress:
                progress(
                    "ocr:error",
                    {
                        "label": f"Erreur OCR ({file_meta.filename})",
                        "file": file_meta.filename,
                        "position": index,
                        "total": total_files,
                        "progress": ocr_progress,
                        "error": ocr_result.error,
                    },
                )

            if progress:
                progress(
                    "ocr:complete",
                    {
                        "label": f"OCR terminé ({file_meta.filename})",
                        "file": file_meta.filename,
                        "position": index,
                        "total": total_files,
                        "progress": ocr_progress,
                        "confidence": ocr_result.confidence,
                        "warnings": ocr_result.warnings or None,
                    },
                )

            time.sleep(0.2)

        if progress:
            progress(
                "analysis:complete",
                {
                    "label": "Analyse OCR & vision terminée",
                    "observationCount": len(observations),
                    "progress": 70,
                },
            )

        risk = self.scorer.score(batch_id, observations) if observations else None

        if progress:
            progress(
                "scoring:complete",
                {
                    "label": "Calcul du score de risque effectué",
                    "hasRisk": risk is not None,
                    "score": getattr(risk, "overall", None) if risk else None,
                    "progress": 85,
                },
            )

        return PipelineResult(
            batch_id=batch_id,
            observations=observations,
            ocr_texts=ocr_texts,
            ocr_engine=self._ocr_engine_name,
            risk=risk,
        )
