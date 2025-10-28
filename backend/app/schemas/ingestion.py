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
