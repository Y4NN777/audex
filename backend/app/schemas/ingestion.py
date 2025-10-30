from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    stored_path: str
    metadata: dict[str, Any] | None = None


class ProcessingEventSchema(BaseModel):
    code: str
    label: str
    kind: str
    timestamp: datetime
    progress: int | None = None
    details: dict[str, Any] | None = None


class OCRTextSchema(BaseModel):
    filename: str
    engine: str
    content: str
    confidence: float | None = None
    warnings: list[str] | None = None
    error: str | None = None


class VisionObservationSchema(BaseModel):
    filename: str
    label: str
    severity: str
    confidence: float | None = None
    bbox: list[int] | None = None
    source: str | None = None
    class_name: str | None = None
    extra: dict[str, Any] | None = None
    created_at: datetime | None = None


class BatchResponse(BaseModel):
    batch_id: str = Field(..., description="Unique identifier of the stored batch.")
    files: list[FileMetadata]
    stored_at: datetime
    status: str = Field(..., description="Current status of the batch processing.")
    report_hash: str | None = None
    report_url: str | None = None
    last_error: str | None = None
    timeline: list[ProcessingEventSchema] | None = None
    ocr_texts: list[OCRTextSchema] | None = None
    observations: list[VisionObservationSchema] | None = None
