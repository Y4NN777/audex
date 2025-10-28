from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from app.schemas.ingestion import FileMetadata


class BatchProcessorProtocol(Protocol):
    def enqueue(self, batch_id: str, files: Iterable[FileMetadata]) -> None: ...


@dataclass
class NoOpBatchProcessor(BatchProcessorProtocol):
    """Placeholder batch processor. Will be replaced with real pipeline orchestration."""

    def enqueue(self, batch_id: str, files: Iterable[FileMetadata]) -> None:
        # In future iterations this will trigger OCR/vision pipelines.
        return None


def get_batch_processor() -> BatchProcessorProtocol:
    return NoOpBatchProcessor()
