from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Iterable, List

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

            if file_meta.content_type.startswith("image/"):
                observations.extend(detect_anomalies(path))
                ocr_texts.append(OCRResult(source_file=file_meta.filename, text=extract_text(path)))
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
            elif file_meta.content_type == "application/pdf":
                ocr_texts.append(
                    OCRResult(
                        source_file=file_meta.filename,
                        text="[pdf-ingestion-pending]",
                    )
                )
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
            elif file_meta.content_type in {
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }:
                ocr_texts.append(
                    OCRResult(
                        source_file=file_meta.filename,
                        text="[docx-ingestion-pending]",
                    )
                )
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
            else:
                # Text files are stored directly as pseudo OCR output
                try:
                    ocr_texts.append(
                        OCRResult(source_file=file_meta.filename, text=path.read_text(encoding="utf-8"))
                    )
                except Exception:
                    ocr_texts.append(OCRResult(source_file=file_meta.filename, text=""))
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

            if progress:
                progress(
                    "ocr:complete",
                    {
                        "label": f"OCR terminé ({file_meta.filename})",
                        "file": file_meta.filename,
                        "position": index,
                        "total": total_files,
                        "progress": ocr_progress,
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

        return PipelineResult(batch_id=batch_id, observations=observations, ocr_texts=ocr_texts, risk=risk)
