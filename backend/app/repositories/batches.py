from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditBatch, BatchFile, GeminiAnalysis, OCRText, ProcessingEvent, VisionObservation
from app.schemas.ingestion import FileMetadata


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_batch(
    session: AsyncSession,
    batch_id: str,
    status: str,
    files: Iterable[FileMetadata],
    created_at: datetime | None = None,
) -> AuditBatch:
    created = created_at or _utcnow()
    db_batch = AuditBatch(id=batch_id, status=status, created_at=created, updated_at=created)
    session.add(db_batch)
    await session.flush()

    for file_meta in files:
        session.add(
            BatchFile(
                batch_id=batch_id,
                filename=file_meta.filename,
                content_type=file_meta.content_type,
                size_bytes=file_meta.size_bytes,
                checksum_sha256=file_meta.checksum_sha256,
                stored_path=file_meta.stored_path,
                metadata_json=file_meta.metadata,
            )
        )

    await session.commit()
    await session.refresh(db_batch, attribute_names=["files"])
    return db_batch


async def update_batch(
    session: AsyncSession,
    batch_id: str,
    *,
    status: str | None = None,
    report_path: str | None = None,
    report_hash: str | None = None,
    last_error: str | None = None,
    gemini_status: str | None = None,
    gemini_summary: str | None = None,
    gemini_prompt_hash: str | None = None,
    gemini_model: str | None = None,
) -> None:
    result = await session.execute(select(AuditBatch).where(AuditBatch.id == batch_id))
    try:
        batch = result.scalar_one()
    except NoResultFound as exc:  # pragma: no cover - defensive branch
        raise RuntimeError(f"Batch {batch_id} not found") from exc

    if status is not None:
        batch.status = status
    if report_path is not None:
        batch.report_path = report_path
    if report_hash is not None:
        batch.report_hash = report_hash
    if last_error is not None:
        batch.last_error = last_error
    if gemini_status is not None:
        batch.gemini_status = gemini_status
    if gemini_summary is not None:
        batch.gemini_summary = gemini_summary
    if gemini_prompt_hash is not None:
        batch.gemini_prompt_hash = gemini_prompt_hash
    if gemini_model is not None:
        batch.gemini_model = gemini_model
    batch.updated_at = _utcnow()
    await session.commit()


async def append_event(
    session: AsyncSession,
    batch_id: str,
    *,
    code: str,
    label: str,
    kind: str,
    timestamp: datetime,
    progress: int | None,
    details: dict | None,
) -> ProcessingEvent:
    db_event = ProcessingEvent(
        batch_id=batch_id,
        code=code,
        label=label,
        kind=kind,
        timestamp=timestamp,
        progress=progress,
        details=details,
    )
    session.add(db_event)
    await session.commit()
    return db_event


async def get_batch(session: AsyncSession, batch_id: str) -> AuditBatch | None:
    result = await session.execute(select(AuditBatch).where(AuditBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if batch:
        await session.refresh(
            batch,
            attribute_names=["files", "events", "ocr_texts", "observations", "gemini_analyses"],
        )
    return batch


async def list_events(session: AsyncSession, batch_id: str) -> Sequence[ProcessingEvent]:
    result = await session.execute(
        select(ProcessingEvent).where(ProcessingEvent.batch_id == batch_id).order_by(ProcessingEvent.timestamp)
    )
    return result.scalars().all()


async def add_events(
    session: AsyncSession,
    batch_id: str,
    events: Sequence[dict],
) -> None:
    if not events:
        return
    session.add_all(
        [
            ProcessingEvent(
                batch_id=batch_id,
                code=event["code"],
                label=event["label"],
                kind=event.get("kind", "info"),
                timestamp=event["timestamp"],
                progress=event.get("progress"),
                details=event.get("details"),
            )
            for event in events
        ]
    )
    await session.commit()


async def replace_ocr_texts(
    session: AsyncSession,
    batch_id: str,
    ocr_entries: Iterable,
    engine_id: str | None = None,
) -> None:
    await session.execute(delete(OCRText).where(OCRText.batch_id == batch_id))

    engine_name = (engine_id or "unknown").lower()
    to_persist = []
    for entry in ocr_entries:
        if hasattr(entry, "source_file") and hasattr(entry, "text"):
            filename = entry.source_file  # type: ignore[attr-defined]
            content = entry.text  # type: ignore[attr-defined]
            confidence = getattr(entry, "confidence", None)
            warnings = getattr(entry, "warnings", None)
            error = getattr(entry, "error", None)
        elif isinstance(entry, dict):
            filename = entry.get("source_file") or entry.get("filename") or "unknown"
            content = entry.get("text", "")
            confidence = entry.get("confidence")
            warnings = entry.get("warnings")
            error = entry.get("error")
        else:
            continue
        warnings_iter: list[str] | None = None
        if warnings is not None and isinstance(warnings, Iterable) and not isinstance(warnings, (str, bytes)):
            warnings_iter = [str(item) for item in warnings if item is not None]

        try:
            confidence_value = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence_value = None

        to_persist.append(
            OCRText(
                batch_id=batch_id,
                filename=str(filename),
                engine=engine_name,
                content=str(content or ""),
                confidence=confidence_value,
                warnings=warnings_iter,
                error=str(error) if error else None,
            )
        )

    if to_persist:
        session.add_all(to_persist)
    await session.commit()


async def replace_observations(
    session: AsyncSession,
    batch_id: str,
    observations: Iterable,
    source: str = "local",
    *,
    replace_existing: bool = True,
    clear_source: str | None = None,
) -> None:
    if replace_existing:
        delete_query = delete(VisionObservation).where(VisionObservation.batch_id == batch_id)
        if clear_source:
            delete_query = delete_query.where(VisionObservation.source == clear_source)
        await session.execute(delete_query)

    to_persist = []
    for entry in observations:
        if hasattr(entry, "source_file") and hasattr(entry, "label"):
            filename = entry.source_file  # type: ignore[attr-defined]
            label = entry.label  # type: ignore[attr-defined]
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
            continue

        try:
            confidence_value = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence_value = None

        bbox_value = None
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            try:
                bbox_value = [int(float(coord)) for coord in bbox]
            except (TypeError, ValueError):
                bbox_value = None

        class_name = None
        extra_payload = None
        if isinstance(extra, dict):
            extra_payload = extra
            class_name = extra.get("class_name")

        to_persist.append(
            VisionObservation(
                batch_id=batch_id,
                filename=str(filename),
                label=str(label),
                severity=str(severity),
                confidence=confidence_value,
                bbox=bbox_value,
                source=source,
                class_name=class_name,
                extra=extra_payload,
            )
        )

    if to_persist:
        session.add_all(to_persist)
    await session.commit()


async def add_gemini_analysis(
    session: AsyncSession,
    batch_id: str,
    *,
    provider: str,
    model: str,
    status: str,
    prompt_hash: str | None,
    prompt_version: str | None,
    duration_ms: int | None,
    summary: str | None,
    warnings: Iterable[str] | None,
    observations_json: Iterable | None,
    raw_response: object | None,
    requested_by: str | None = None,
) -> GeminiAnalysis:
    record = GeminiAnalysis(
        batch_id=batch_id,
        provider=provider,
        model=model,
        status=status,
        prompt_hash=prompt_hash,
        prompt_version=prompt_version,
        duration_ms=duration_ms,
        summary=summary,
        warnings=list(warnings) if warnings is not None else None,
        observations_json=list(observations_json) if observations_json is not None else None,
        raw_response=raw_response,
        requested_by=requested_by,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def list_gemini_analyses(session: AsyncSession, batch_id: str) -> Sequence[GeminiAnalysis]:
    result = await session.execute(
        select(GeminiAnalysis).where(GeminiAnalysis.batch_id == batch_id).order_by(GeminiAnalysis.created_at.desc())
    )
    return result.scalars().all()


async def get_latest_gemini_analysis(session: AsyncSession, batch_id: str) -> GeminiAnalysis | None:
    result = await session.execute(
        select(GeminiAnalysis)
        .where(GeminiAnalysis.batch_id == batch_id)
        .order_by(GeminiAnalysis.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()
