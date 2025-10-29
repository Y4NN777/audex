from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
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

ALLOWED_CONTENT_TYPES: Iterable[str] = ("image/", "application/pdf", "text/plain")


def get_storage_root() -> Path:
    return Path(settings.STORAGE_PATH)


def get_processor(storage_root: Path = Depends(get_storage_root)) -> BatchProcessorProtocol:
    return get_batch_processor(storage_root)


@router.post("/batches", summary="Upload a batch of audit files", response_model=BatchResponse)
async def create_batch(
    files: list[UploadFile],
    storage_root: Path = Depends(get_storage_root),
    processor: BatchProcessorProtocol = Depends(get_processor),
) -> BatchResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided.")

    batch_id = uuid4().hex
    batch_dir = storage_root / batch_id
    stored_files: list[FileMetadata] = []

    storage_root.mkdir(parents=True, exist_ok=True)

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
    await event_bus.publish({"batchId": batch_id, "status": "processing"})

    processor.enqueue(batch_id, stored_files)

    pipeline = IngestionPipeline(storage_root)
    reports_dir = storage_root / "reports"
    report_builder = ReportBuilder(reports_dir)

    try:
        pipeline_result = pipeline.run(batch_id, stored_files)
        artifact = report_builder.build_from_pipeline(pipeline_result)
        await batch_store.update_batch(
            batch_id,
            status="completed",
            report_path=artifact.path,
            report_hash=artifact.checksum_sha256,
        )
        await event_bus.publish(
            {
                "batchId": batch_id,
                "status": "completed",
                "reportHash": artifact.checksum_sha256,
                "reportUrl": f"/api/v1/ingestion/reports/{batch_id}"
            }
        )
        return BatchResponse(
            batch_id=batch_id,
            files=stored_files,
            stored_at=created_at,
            status="completed",
            report_hash=artifact.checksum_sha256,
        )
    except Exception as exc:  # noqa: BLE001
        await batch_store.update_batch(batch_id, status="failed", last_error=str(exc))
        await event_bus.publish({"batchId": batch_id, "status": "failed", "error": str(exc)})
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
