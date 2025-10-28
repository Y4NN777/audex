from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.ingestion import BatchResponse, FileMetadata
from app.services.metadata import extract_image_metadata
from app.services.storage import allowed_content_type, sanitize_filename, save_upload_file

router = APIRouter()

ALLOWED_CONTENT_TYPES: Iterable[str] = ("image/", "application/pdf", "text/plain")


def get_storage_root() -> Path:
    return Path(settings.STORAGE_PATH)


@router.post("/batches", summary="Upload a batch of audit files", response_model=BatchResponse)
async def create_batch(
    files: list[UploadFile],
    storage_root: Path = Depends(get_storage_root),
) -> BatchResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided.")

    batch_id = uuid4().hex
    batch_dir = storage_root / batch_id
    stored_files: list[FileMetadata] = []

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

    return BatchResponse(batch_id=batch_id, files=stored_files, stored_at=datetime.now(tz=timezone.utc))
