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


class BatchResponse(BaseModel):
    batch_id: str = Field(..., description="Unique identifier of the stored batch.")
    files: list[FileMetadata]
    stored_at: datetime
    status: str = Field(..., description="Current status of the batch processing.")
    report_hash: str | None = None
    report_url: str | None = None
    timeline: list[dict[str, Any]] | None = None
