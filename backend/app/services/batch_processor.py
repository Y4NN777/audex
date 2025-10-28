from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from app.schemas.ingestion import FileMetadata
from app.services.pipeline import IngestionPipeline


class BatchProcessorProtocol(Protocol):
    def enqueue(self, batch_id: str, files: Iterable[FileMetadata]) -> None: ...


@dataclass
class LocalPipelineBatchProcessor(BatchProcessorProtocol):
    """Runs the ingestion pipeline synchronously (MVP)."""

    storage_root: Path

    def __post_init__(self) -> None:
        self.pipeline = IngestionPipeline(self.storage_root)

    def enqueue(self, batch_id: str, files: Iterable[FileMetadata]) -> None:
        self.pipeline.run(batch_id, list(files))


def get_batch_processor(storage_root: Path) -> BatchProcessorProtocol:
    return LocalPipelineBatchProcessor(storage_root)
