from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Any, Callable, Iterable, List, Sequence

from app.pipelines.models import OCRResult, Observation, PipelineResult
from app.services.scoring import RiskScorer
from app.services.ocr_engine import get_ocr_engine
from app.services.vision_engine import get_vision_engine
from app.services.advanced_analyzer import AdvancedAnalyzer
from app.services.report_summary import ReportSummaryService, SummaryRequest
from app.schemas.ingestion import FileMetadata

logger = logging.getLogger(__name__)


# Simulated delays (demo mode) to make pipeline progression perceptible during tests.
# These values intentionally stretch processing so stakeholders can observe each stage.
SIMULATED_METADATA_DELAY_SECONDS = 15.0
SIMULATED_ANALYSIS_DELAY_SECONDS = 30.0
SIMULATED_SCORING_DELAY_SECONDS = 20.0
SIMULATED_SUMMARY_DELAY_SECONDS = 30.0
SIMULATED_REPORT_DELAY_SECONDS = 15.0


class IngestionPipeline:
    """Orchestrates OCR + vision inference to produce structured outputs."""

    def __init__(
        self,
        storage_root: Path,
        scorer: RiskScorer | None = None,
        advanced_analyzer: AdvancedAnalyzer | None = None,
        summary_service: ReportSummaryService | None = None,
        *,
        simulate_latency: bool = False,
    ) -> None:
        self.storage_root = storage_root
        self.scorer = scorer or RiskScorer()
        self._ocr_engine = get_ocr_engine()
        self._vision_engine = get_vision_engine()
        self._ocr_engine_name = getattr(self._ocr_engine, "engine_id", "unknown")
        self._advanced_analyzer = advanced_analyzer or AdvancedAnalyzer()
        self._summary_service = summary_service or ReportSummaryService()
        self._simulate_latency = simulate_latency

    @property
    def simulate_latency_enabled(self) -> bool:
        return self._simulate_latency

    def _sleep(self, seconds: float) -> None:
        if self._simulate_latency and seconds > 0:
            time.sleep(seconds)

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

        logger.info("Pipeline run started for batch %s (%d file(s))", batch_id, total_files)

        def emit(stage: str, data: dict[str, Any]) -> None:
            if progress:
                progress(stage, data)

        ocr_status_callback = getattr(self._ocr_engine, "set_status_callback", None)
        if callable(ocr_status_callback):
            try:
                ocr_status_callback(emit)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Unable to attach OCR status callback: %s", exc)

        if progress:
            progress(
                "analysis:start",
                {
                    "label": "Analyse OCR & vision démarrée",
                    "fileCount": total_files,
                    "progress": 25,
                },
            )

        status_interval = 30.0
        last_status_update = time.monotonic() - status_interval

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

            logger.debug(
                "Processing file %s [%s] (image=%s)",
                file_meta.filename,
                file_meta.content_type,
                is_image,
            )

            if is_image:
                metadata = file_meta.metadata or {}
                zone_name = metadata.get("zone") or metadata.get("area") or metadata.get("location")
                if isinstance(zone_name, str):
                    zone_value = zone_name
                else:
                    zone_value = None

                observations.extend(self._vision_engine.detect(path, zone=zone_value))
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

                now = time.monotonic()
                if now - last_status_update >= status_interval:
                    progress(
                        "analysis:status",
                        {
                            "label": f"Analyse en cours ({file_meta.filename})",
                            "file": file_meta.filename,
                            "position": index,
                            "total": total_files,
                            "progress": max(ocr_progress, 55),
                        },
                    )
                    last_status_update = now

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
            self._sleep(SIMULATED_ANALYSIS_DELAY_SECONDS)

        logger.info("Vision/OCR completed for batch %s (observations=%d)", batch_id, len(observations))

        risk = self.scorer.score(batch_id, observations) if observations else None

        if progress:
            progress(
                "scoring:complete",
                {
                    "label": "Calcul du score de risque effectué",
                    "hasRisk": risk is not None,
                    "score": getattr(risk, "total_score", None) if risk else None,
                    "progress": 85,
                },
            )
            self._sleep(SIMULATED_SCORING_DELAY_SECONDS)

        local_observations = list(observations)

        image_files_with_zone: list[tuple[Path, str | None]] = []
        for meta in file_list:
            if meta.content_type.startswith("image/"):
                zone_name = None
                site_type = None
                if meta.metadata:
                    zone_name = (
                        meta.metadata.get("zone")
                        or meta.metadata.get("area")
                        or meta.metadata.get("location")
                    )
                    site_type = meta.metadata.get("site_type") or meta.metadata.get("siteType")
                image_files_with_zone.append(
                    (
                        Path(meta.stored_path),
                        zone_name if isinstance(zone_name, str) else None,
                        site_type if isinstance(site_type, str) else None,
                    )
                )

        gemini_result = self._advanced_analyzer.analyze(batch_id, image_files_with_zone)
        gemini_observations = gemini_result.observations

        logger.info(
            "Advanced analyzer completed for batch %s (status=%s, obs=%d, warnings=%d)",
            batch_id,
            gemini_result.status,
            len(gemini_observations),
            len(gemini_result.warnings),
        )

        combined_observations = local_observations + gemini_observations

        summary_result = self._summary_service.generate(
            SummaryRequest(
                batch_id=batch_id,
                risk=risk,
                observations_local=local_observations,
                observations_gemini=gemini_observations,
                ocr_texts=ocr_texts,
            )
        )

        if progress:
            progress(
                "summary:complete",
                {
                    "label": "Synthèse IA générée",
                    "status": summary_result.status,
                    "progress": 90,
                },
            )
            self._sleep(SIMULATED_SUMMARY_DELAY_SECONDS)

        result = PipelineResult(
            batch_id=batch_id,
            observations=combined_observations,
            ocr_texts=ocr_texts,
            ocr_engine=self._ocr_engine_name,
            observations_local=local_observations,
            observations_gemini=gemini_observations,
            gemini_summary=gemini_result.summary,
            gemini_status=gemini_result.status,
            gemini_warnings=gemini_result.warnings or None,
            gemini_prompt_hash=gemini_result.prompt_hash,
            gemini_duration_ms=gemini_result.duration_ms,
            gemini_payloads=gemini_result.payloads or None,
            gemini_model=gemini_result.model,
            gemini_provider=gemini_result.provider,
            gemini_prompt_version=gemini_result.prompt_version,
            risk=risk,
            summary_text=summary_result.text,
            summary_status=summary_result.status,
            summary_source=summary_result.source,
            summary_findings=summary_result.findings,
            summary_recommendations=summary_result.recommendations,
            summary_prompt_hash=summary_result.prompt_hash,
            summary_response_hash=summary_result.response_hash,
            summary_duration_ms=summary_result.duration_ms,
            summary_warnings=summary_result.warnings or None,
        )

        if callable(ocr_status_callback):
            try:
                ocr_status_callback(None)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Unable to reset OCR status callback: %s", exc)

        return result
