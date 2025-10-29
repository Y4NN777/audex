from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.schemas.ingestion import FileMetadata


@dataclass
class BatchRecord:
    id: str
    created_at: datetime
    status: str
    files: list[FileMetadata] = field(default_factory=list)
    report_path: Path | None = None
    report_hash: str | None = None
    last_error: str | None = None


class BatchStore:
    def __init__(self) -> None:
        self._records: dict[str, BatchRecord] = {}
        self._lock = asyncio.Lock()

    async def set_batch(self, record: BatchRecord) -> None:
        async with self._lock:
            self._records[record.id] = record

    async def update_batch(
        self,
        batch_id: str,
        *,
        status: str | None = None,
        report_path: Path | None = None,
        report_hash: str | None = None,
        last_error: str | None = None,
    ) -> None:
        async with self._lock:
            record = self._records.get(batch_id)
            if not record:
                return
            if status is not None:
                record.status = status
            if report_path is not None:
                record.report_path = report_path
            if report_hash is not None:
                record.report_hash = report_hash
            if last_error is not None:
                record.last_error = last_error
            self._records[batch_id] = record

    async def get(self, batch_id: str) -> BatchRecord | None:
        async with self._lock:
            return self._records.get(batch_id)


batch_store = BatchStore()
