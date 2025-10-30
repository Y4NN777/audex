from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.models import AuditBatch, GeminiAnalysis
from app.repositories import batches as batch_repo
from app.schemas.ingestion import (
    BatchResponse,
    BatchSummarySchema,
    FileMetadata,
    GeminiAnalysisRecord,
    GeminiAnalysisRequest,
    GeminiAnalysisResponse,
    ProcessingEventSchema,
    RiskBreakdownSchema,
    RiskScoreSchema,
)
from app.services.batch_processor import BatchProcessorProtocol, get_batch_processor
from app.services.events import event_bus
from app.services.metadata import extract_image_metadata
from app.services.pipeline import IngestionPipeline
from app.services.report import ReportBuilder
from app.services.storage import allowed_content_type, sanitize_filename, save_upload_file
from app.services.advanced_analyzer import AdvancedAnalyzer

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES: Iterable[str] = (
    "image/",
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)


def get_storage_root() -> Path:
    return Path(settings.STORAGE_PATH)


def get_processor(storage_root: Path = Depends(get_storage_root)) -> BatchProcessorProtocol:
    return get_batch_processor(storage_root)


def _observation_payload(entry: Any, source: str) -> dict[str, Any]:
    if hasattr(entry, "source_file"):
        filename = entry.source_file  # type: ignore[attr-defined]
        label = getattr(entry, "label", "general")
        severity = getattr(entry, "severity", "medium")
        confidence = getattr(entry, "confidence", None)
        bbox = getattr(entry, "bbox", None)
        extra = getattr(entry, "extra", None)
    elif isinstance(entry, dict):
        filename = entry.get("source_file") or entry.get("filename") or "unknown"
        label = entry.get("label", "general")
        severity = entry.get("severity", "medium")
        confidence = entry.get("confidence")
        bbox = entry.get("bbox")
        extra = entry.get("extra")
    else:
        filename = "unknown"
        label = "general"
        severity = "medium"
        confidence = None
        bbox = None
        extra = None

    bbox_payload: list[int] | None = None
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            bbox_payload = [int(float(coord)) for coord in bbox]
        except (TypeError, ValueError):
            bbox_payload = None

    extra_payload = extra if isinstance(extra, dict) else None

    return {
        "source": source,
        "source_file": str(filename),
        "label": str(label),
        "severity": str(severity),
        "confidence": float(confidence) if isinstance(confidence, (int, float)) else None,
        "bbox": bbox_payload,
        "extra": extra_payload,
    }


def _serialize_gemini_record(record: GeminiAnalysis) -> GeminiAnalysisRecord:
    return GeminiAnalysisRecord(
        id=record.id or 0,
        status=record.status,
        summary=record.summary,
        warnings=record.warnings,
        prompt_hash=record.prompt_hash,
        prompt_version=record.prompt_version,
        provider=record.provider,
        model=record.model,
        duration_ms=record.duration_ms,
        requested_by=record.requested_by,
        created_at=record.created_at,
        observations=record.observations_json,
        raw_response=record.raw_response,
    )


@router.post("/batches", summary="Upload a batch of audit files", response_model=BatchResponse)
async def create_batch(
    files: list[UploadFile],
    client_batch_id: str | None = Form(None),
    storage_root: Path = Depends(get_storage_root),
    session: AsyncSession = Depends(get_session),
    processor: BatchProcessorProtocol = Depends(get_processor),
) -> BatchResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided.")

    if client_batch_id:
        candidate = sanitize_filename(client_batch_id)
        batch_id = candidate or uuid4().hex
    else:
        batch_id = uuid4().hex
    batch_dir = storage_root / batch_id
    stored_files: list[FileMetadata] = []

    storage_root.mkdir(parents=True, exist_ok=True)

    timeline_events: list[dict[str, Any]] = []
    db_event_records: list[dict[str, Any]] = []
    stage_progress_map: dict[str, int] = {
        "ingestion:received": 5,
        "metadata:extracted": 15,
        "analysis:start": 25,
        "vision:start": 30,
        "vision:complete": 45,
        "ocr:start": 55,
        "ocr:complete": 70,
        "ocr:error": 70,
        "analysis:complete": 75,
        "scoring:complete": 85,
        "report:generated": 95,
        "report:available": 100,
        "pipeline:error": 100,
    }

    def resolve_progress(stage_code: str, details: dict[str, Any] | None, explicit: int | None) -> int | None:
        if explicit is not None:
            return explicit
        return stage_progress_map.get(stage_code)

    def build_stage(
        stage_code: str,
        label: str,
        *,
        kind: str = "info",
        details: dict[str, Any] | None = None,
        progress: int | None = None,
    ) -> dict[str, Any]:
        timestamp = datetime.now(tz=timezone.utc)
        stage: dict[str, Any] = {
            "eventId": uuid4().hex,
            "code": stage_code,
            "label": label,
            "kind": kind,
            "timestamp": timestamp.isoformat(),
        }
        if details:
            stage["details"] = details
        resolved_progress = resolve_progress(stage_code, details, progress)
        if resolved_progress is not None:
            stage["progress"] = max(0, min(100, resolved_progress))
        timeline_events.append(stage)
        db_event_records.append(
            {
                "code": stage_code,
                "label": label,
                "kind": kind,
                "timestamp": timestamp,
                "progress": stage.get("progress"),
                "details": details,
            }
        )
        return stage

    async def publish_stage(stage: dict[str, Any]) -> None:
        await event_bus.publish({"batchId": batch_id, "stage": stage})

    async def emit_stage(
        stage_code: str,
        label: str,
        *,
        kind: str = "info",
        details: dict[str, Any] | None = None,
        progress: int | None = None,
    ) -> None:
        stage = build_stage(stage_code, label, kind=kind, details=details, progress=progress)
        await publish_stage(stage)

    def schedule_stage(
        stage_code: str,
        label: str,
        *,
        kind: str = "info",
        details: dict[str, Any] | None = None,
        progress: int | None = None,
    ) -> None:
        stage = build_stage(stage_code, label, kind=kind, details=details, progress=progress)
        asyncio.create_task(publish_stage(stage))

    for upload in files:
        if not allowed_content_type(upload.content_type or "", ALLOWED_CONTENT_TYPES):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported content type: {upload.content_type}",
            )

        safe_name = sanitize_filename(upload.filename or "file")
        destination = batch_dir / safe_name

        size, checksum = await save_upload_file(upload, destination)

        metadata = None
        if (upload.content_type or "").startswith("image/"):
            metadata = extract_image_metadata(destination)

        stored_files.append(
            FileMetadata(
                filename=safe_name,
                content_type=upload.content_type or "application/octet-stream",
                size_bytes=size,
                checksum_sha256=checksum,
                stored_path=str(destination),
                metadata=metadata or None,
            )
        )

    created_at = datetime.now(tz=timezone.utc)
    await batch_repo.create_batch(session, batch_id, "processing", stored_files, created_at)
    await emit_stage(
        "ingestion:received",
        "Fichiers reçus et stockés",
        details={"fileCount": len(stored_files)},
    )
    await event_bus.publish({"batchId": batch_id, "status": "processing"})

    processor.enqueue(batch_id, stored_files)

    pipeline = IngestionPipeline(storage_root)
    reports_dir = storage_root / "reports"
    report_builder = ReportBuilder(reports_dir)

    async def persist_events() -> None:
        if db_event_records:
            await batch_repo.add_events(session, batch_id, db_event_records.copy())
            db_event_records.clear()

    try:
        await emit_stage(
            "metadata:extracted",
            "Métadonnées extraites pour tous les fichiers",
            details={"hasMetadata": any(file.metadata for file in stored_files)},
        )

        pipeline_result = pipeline.run(
            batch_id,
            stored_files,
            progress=lambda stage, data: schedule_stage(
                stage,
                data.get("label", stage),
                details={k: v for k, v in data.items() if k not in {"label", "progress"}},
                progress=int(data["progress"]) if "progress" in data else None,
            ),
        )
        await batch_repo.replace_observations(
            session,
            batch_id,
            pipeline_result.observations_local or [],
            source="local",
            replace_existing=True,
        )
        if pipeline_result.risk:
            await batch_repo.save_risk_score(
                session,
                batch_id,
                total_score=pipeline_result.risk.total_score,
                normalized_score=pipeline_result.risk.normalized_score,
                breakdown=pipeline_result.risk.breakdown,
            )
        else:
            await batch_repo.delete_risk_score(session, batch_id)
        await batch_repo.save_report_summary(
            session,
            batch_id,
            summary_text=pipeline_result.summary_text,
            findings=pipeline_result.summary_findings,
            recommendations=pipeline_result.summary_recommendations,
            status=pipeline_result.summary_status or "disabled",
            source=pipeline_result.summary_source,
            warnings=pipeline_result.summary_warnings or [],
            prompt_hash=pipeline_result.summary_prompt_hash,
            response_hash=pipeline_result.summary_response_hash,
            duration_ms=pipeline_result.summary_duration_ms,
        )
        gemini_observation_payload = (
            [_observation_payload(obs, "gemini") for obs in pipeline_result.observations_gemini]
            if pipeline_result.observations_gemini
            else None
        )
        if pipeline_result.observations_gemini:
            await batch_repo.replace_observations(
                session,
                batch_id,
                pipeline_result.observations_gemini,
                source="gemini",
                replace_existing=False,
            )
        await batch_repo.replace_ocr_texts(session, batch_id, pipeline_result.ocr_texts, pipeline_result.ocr_engine)
        await batch_repo.add_gemini_analysis(
            session,
            batch_id,
            provider=pipeline_result.gemini_provider or "google-gemini",
            model=pipeline_result.gemini_model or settings.GEMINI_MODEL,
            status=pipeline_result.gemini_status or ("disabled" if not settings.GEMINI_ENABLED else "unknown"),
            prompt_hash=pipeline_result.gemini_prompt_hash,
            prompt_version=pipeline_result.gemini_prompt_version,
            duration_ms=pipeline_result.gemini_duration_ms,
            summary=pipeline_result.gemini_summary,
            warnings=pipeline_result.gemini_warnings or [],
            observations_json=gemini_observation_payload,
            raw_response=pipeline_result.gemini_payloads,
            requested_by="pipeline:auto",
        )
        artifact = report_builder.build_from_pipeline(
            pipeline_result,
            timeline=timeline_events,
            storage_root=storage_root,
        )
        await emit_stage(
            "report:generated",
            "Rapport PDF généré",
            kind="success",
            details={"hash": artifact.checksum_sha256, "path": str(artifact.path)},
            progress=95,
        )
        await batch_repo.update_batch(
            session,
            batch_id,
            status="completed",
            report_path=str(artifact.path),
            report_hash=artifact.checksum_sha256,
            gemini_status=pipeline_result.gemini_status,
            gemini_summary=pipeline_result.gemini_summary,
            gemini_prompt_hash=pipeline_result.gemini_prompt_hash,
            gemini_model=pipeline_result.gemini_model or settings.GEMINI_MODEL,
        )
        final_stage = build_stage(
            "report:available",
            "Rapport disponible au téléchargement",
            kind="success",
            details={"hash": artifact.checksum_sha256},
            progress=100,
        )
        report_path_fragment = f"{settings.API_V1_PREFIX}/ingestion/reports/{batch_id}"
        await event_bus.publish(
            {
                "batchId": batch_id,
                "status": "completed",
                "reportHash": artifact.checksum_sha256,
                "reportUrl": report_path_fragment,
                "stage": final_stage,
            }
        )
        await persist_events()
        batch = await batch_repo.get_batch(session, batch_id)
        if not batch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
        return _serialize_batch(batch)
    except Exception as exc:  # noqa: BLE001
        await batch_repo.update_batch(session, batch_id, status="failed", last_error=str(exc))
        error_stage = build_stage(
            "pipeline:error",
            "Erreur durant le traitement",
            kind="error",
            details={"message": str(exc)},
        )
        await event_bus.publish(
            {
                "batchId": batch_id,
                "status": "failed",
                "error": str(exc),
                "stage": error_stage,
            }
        )
        await persist_events()
        raise HTTPException(status_code=500, detail="Batch processing failed") from exc
    finally:
        await persist_events()


async def _event_stream(request: Request, queue: asyncio.Queue[str], interval: float = 15.0):
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                message = await asyncio.wait_for(queue.get(), timeout=interval)
            except asyncio.TimeoutError:
                yield "event: keepalive\ndata: {}\n\n"
            else:
                yield f"data: {message}\n\n"
    finally:
        await event_bus.unsubscribe(queue)


@router.get("/events", summary="Server-sent events pour l'état des lots")
async def ingestion_events(request: Request) -> StreamingResponse:
    queue = await event_bus.subscribe()
    return StreamingResponse(_event_stream(request, queue), media_type="text/event-stream")


@router.get("/batches/{batch_id}", summary="Récupérer un lot et sa timeline", response_model=BatchResponse)
async def read_batch(batch_id: str, session: AsyncSession = Depends(get_session)) -> BatchResponse:
    batch = await batch_repo.get_batch(session, batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return _serialize_batch(batch)


@router.get("/reports/{batch_id}", summary="Télécharger le rapport généré")
async def download_report(batch_id: str, session: AsyncSession = Depends(get_session)) -> FileResponse:
    record = await batch_repo.get_batch(session, batch_id)
    if not record or not record.report_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    report_path = Path(record.report_path)
    if not report_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    filename = report_path.name
    return FileResponse(report_path, media_type="application/pdf", filename=filename)


@router.get(
    "/batches/{batch_id}/analysis",
    summary="Consulter l'analyse Gemini d'un lot",
    response_model=GeminiAnalysisResponse,
)
async def get_batch_analysis(
    batch_id: str,
    include_history: bool = False,
    session: AsyncSession = Depends(get_session),
) -> GeminiAnalysisResponse:
    batch = await batch_repo.get_batch(session, batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    analyses = await batch_repo.list_gemini_analyses(session, batch_id)
    if not analyses:
        return GeminiAnalysisResponse(latest=None, history=[] if include_history else None)

    latest_record = _serialize_gemini_record(analyses[0])
    history = [_serialize_gemini_record(item) for item in analyses] if include_history else None
    return GeminiAnalysisResponse(latest=latest_record, history=history)


@router.post(
    "/batches/{batch_id}/analysis",
    summary="Relancer l'analyse Gemini d'un lot existant",
    response_model=GeminiAnalysisRecord,
)
async def rerun_batch_analysis(
    batch_id: str,
    payload: GeminiAnalysisRequest | None = None,
    storage_root: Path = Depends(get_storage_root),
    session: AsyncSession = Depends(get_session),
) -> GeminiAnalysisRecord:
    batch = await batch_repo.get_batch(session, batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    analyzer = AdvancedAnalyzer()
    if not analyzer.enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Gemini analysis disabled.")
    if not analyzer.api_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Gemini API key missing.")

    image_records: list[tuple[Path, str | None, str | None]] = []
    for file in batch.files:
        if not file.content_type or not file.content_type.startswith("image/"):
            continue
        stored_path = Path(file.stored_path)
        if not stored_path.exists():
            fallback_path = storage_root / file.filename
            if fallback_path.exists():
                stored_path = fallback_path
            else:
                logger.warning("Image %s introuvable pour batch %s.", file.stored_path, batch_id)
                continue
        metadata = file.metadata_json or {}
        zone_val = metadata.get("zone") or metadata.get("area") or metadata.get("location")
        site_type = metadata.get("site_type") or metadata.get("siteType")
        image_records.append(
            (
                stored_path,
                zone_val if isinstance(zone_val, str) else None,
                site_type if isinstance(site_type, str) else None,
            )
        )

    if not image_records:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No image files available for analysis.")

    result = analyzer.analyze(batch_id, image_records)
    gemini_observations = result.observations or []
    gemini_payload = [_observation_payload(obs, "gemini") for obs in gemini_observations] if gemini_observations else None

    await batch_repo.replace_observations(
        session,
        batch_id,
        gemini_observations,
        source="gemini",
        replace_existing=True,
        clear_source="gemini",
    )

    record = await batch_repo.add_gemini_analysis(
        session,
        batch_id,
        provider=result.provider,
        model=result.model or analyzer.model,
        status=result.status,
        prompt_hash=result.prompt_hash,
        prompt_version=result.prompt_version,
        duration_ms=result.duration_ms,
        summary=result.summary,
        warnings=result.warnings,
        observations_json=gemini_payload,
        raw_response=result.payloads,
        requested_by=(payload.requested_by if payload else None) or "api:manual",
    )

    await batch_repo.update_batch(
        session,
        batch_id,
        gemini_status=result.status,
        gemini_summary=result.summary,
        gemini_prompt_hash=result.prompt_hash,
        gemini_model=result.model or analyzer.model,
    )

    return _serialize_gemini_record(record)


def _serialize_batch(batch: AuditBatch) -> BatchResponse:
    files = [
        FileMetadata(
            filename=file.filename,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            checksum_sha256=file.checksum_sha256,
            stored_path=file.stored_path,
            metadata=file.metadata_json,
        )
        for file in batch.files
    ]
    ocr_texts = [
        {
            "filename": text.filename,
            "engine": text.engine,
            "content": text.content,
            "confidence": text.confidence,
            "warnings": text.warnings,
            "error": text.error,
        }
        for text in batch.ocr_texts
    ]
    observations = [
        {
            "filename": obs.filename,
            "label": obs.label,
            "severity": obs.severity,
            "confidence": obs.confidence,
            "bbox": obs.bbox,
            "source": obs.source,
            "class_name": obs.class_name,
            "extra": obs.extra,
            "created_at": obs.created_at,
        }
        for obs in batch.observations
    ]
    timeline = [
        ProcessingEventSchema(
            code=event.code,
            label=event.label,
            kind=event.kind,
            timestamp=event.timestamp,
            progress=event.progress,
            details=event.details,
        )
        for event in batch.events
    ]
    report_url = None
    if batch.report_path:
        report_url = f"{settings.API_V1_PREFIX}/ingestion/reports/{batch.id}"
    risk_schema = None
    summary_schema = None
    if batch.risk_score:
        breakdown_items = batch.risk_score.breakdown or []
        if isinstance(breakdown_items, dict):
            breakdown_iterable = [breakdown_items]
        else:
            breakdown_iterable = breakdown_items if isinstance(breakdown_items, list) else []
        breakdown_schemas = [
            RiskBreakdownSchema(
                label=str(item.get("label", "")),
                severity=str(item.get("severity", "")),
                count=int(item.get("count", 0)),
                score=float(item.get("score", 0.0)),
            )
            for item in breakdown_iterable
            if isinstance(item, dict)
        ]
        risk_schema = RiskScoreSchema(
            total_score=float(batch.risk_score.total_score),
            normalized_score=float(batch.risk_score.normalized_score),
            breakdown=breakdown_schemas,
            created_at=batch.risk_score.created_at,
        )
    if batch.report_summary:
        findings_list = []
        if isinstance(batch.report_summary.findings, list):
            findings_list = [str(item) for item in batch.report_summary.findings]
        recommendations_list = []
        if isinstance(batch.report_summary.recommendations, list):
            recommendations_list = [str(item) for item in batch.report_summary.recommendations]
        warnings_list = []
        if isinstance(batch.report_summary.warnings, list):
            warnings_list = [str(item) for item in batch.report_summary.warnings]
        summary_schema = BatchSummarySchema(
            status=batch.report_summary.status,
            source=batch.report_summary.source,
            text=batch.report_summary.summary_text,
            findings=findings_list or None,
            recommendations=recommendations_list or None,
            warnings=warnings_list or None,
            prompt_hash=batch.report_summary.prompt_hash,
            response_hash=batch.report_summary.response_hash,
            duration_ms=batch.report_summary.duration_ms,
            created_at=batch.report_summary.created_at,
        )
    return BatchResponse(
        batch_id=batch.id,
        files=files,
        stored_at=batch.created_at,
        status=batch.status,
        report_hash=batch.report_hash,
        report_url=report_url,
        last_error=batch.last_error,
        timeline=timeline,
        ocr_texts=ocr_texts,
        observations=observations or None,
        gemini_status=batch.gemini_status,
        gemini_summary=batch.gemini_summary,
        gemini_prompt_hash=batch.gemini_prompt_hash,
        gemini_model=batch.gemini_model,
        risk_score=risk_schema,
        summary=summary_schema,
    )
