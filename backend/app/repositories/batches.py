from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditBatch, BatchFile, ProcessingEvent
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
        await session.refresh(batch, attribute_names=["files", "events"])
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
