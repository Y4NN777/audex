from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import settings
from app.schemas.ingestion import BatchResponse, FileMetadata
from app.services.batch_processor import BatchProcessorProtocol, get_batch_processor
from app.services.events import event_bus
from app.services.metadata import extract_image_metadata
from app.services.pipeline import IngestionPipeline
from app.services.report import ReportBuilder
from app.services.storage import allowed_content_type, sanitize_filename, save_upload_file
from app.services.store import BatchRecord, batch_store

router = APIRouter()

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


@router.post("/batches", summary="Upload a batch of audit files", response_model=BatchResponse)
async def create_batch(
    files: list[UploadFile],
    client_batch_id: str | None = Form(None),
    storage_root: Path = Depends(get_storage_root),
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
    stage_progress_map: dict[str, int] = {
        "ingestion:received": 5,
        "metadata:extracted": 15,
        "analysis:start": 25,
        "vision:start": 30,
        "vision:complete": 45,
        "ocr:start": 55,
        "ocr:complete": 70,
        "analysis:complete": 75,
        "scoring:complete": 85,
        "report:generated": 95,
        "report:available": 100,
        "pipeline:error": 100,
    }

    def resolve_progress(stage_code: str, details: dict[str, Any] | None, explicit: int | None) -> int | None:
        if explicit is not None:
            return explicit
        if stage_code == "analysis:file":
            if not details:
                return None
            total = int(details.get("total") or 0)
            position = int(details.get("position") or 0)
            if total <= 0:
                return None
            # Spread per-file progress between 30 and 65
            base = 30
            span = 40
            ratio = min(max(position / total, 0.0), 1.0)
            return base + int(span * ratio)
        return stage_progress_map.get(stage_code)

    def build_stage(
        stage_code: str,
        label: str,
        *,
        kind: str = "info",
        details: dict[str, Any] | None = None,
        progress: int | None = None,
    ) -> dict[str, Any]:
        stage: dict[str, Any] = {
            "eventId": uuid4().hex,
            "code": stage_code,
            "label": label,
            "kind": kind,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        if details:
            stage["details"] = details
        resolved_progress = resolve_progress(stage_code, details, progress)
        if resolved_progress is not None:
            stage["progress"] = max(0, min(100, resolved_progress))
        timeline_events.append(stage)
        return stage

    async def emit_stage(
        stage_code: str,
        label: str,
        *,
        kind: str = "info",
        details: dict[str, Any] | None = None,
        progress: int | None = None,
    ) -> None:
        stage = build_stage(stage_code, label, kind=kind, details=details, progress=progress)
        await event_bus.publish({"batchId": batch_id, "stage": stage})

    def schedule_stage(
        stage_code: str,
        label: str,
        *,
        kind: str = "info",
        details: dict[str, Any] | None = None,
        progress: int | None = None,
    ) -> None:
        stage = build_stage(stage_code, label, kind=kind, details=details, progress=progress)
        asyncio.create_task(event_bus.publish({"batchId": batch_id, "stage": stage}))

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
    await batch_store.set_batch(
        BatchRecord(id=batch_id, created_at=created_at, status="processing", files=stored_files)
    )
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
        artifact = report_builder.build_from_pipeline(pipeline_result)
        await emit_stage(
            "report:generated",
            "Rapport PDF généré",
            kind="success",
            details={"hash": artifact.checksum_sha256, "path": str(artifact.path)},
            progress=95,
        )
        await batch_store.update_batch(
            batch_id,
            status="completed",
            report_path=artifact.path,
            report_hash=artifact.checksum_sha256,
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
        return BatchResponse(
            batch_id=batch_id,
            files=stored_files,
            stored_at=created_at,
            status="completed",
            report_hash=artifact.checksum_sha256,
            report_url=report_path_fragment,
            timeline=timeline_events,
        )
    except Exception as exc:  # noqa: BLE001
        await batch_store.update_batch(batch_id, status="failed", last_error=str(exc))
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
        raise HTTPException(status_code=500, detail="Batch processing failed") from exc


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


@router.get("/reports/{batch_id}", summary="Télécharger le rapport généré")
async def download_report(batch_id: str) -> FileResponse:
    record = await batch_store.get(batch_id)
    if not record or not record.report_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    filename = record.report_path.name
    return FileResponse(record.report_path, media_type="application/pdf", filename=filename)
