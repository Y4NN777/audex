from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from fastapi import UploadFile


def ensure_directory(path: Path) -> None:
    """Create directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


async def save_upload_file(upload: UploadFile, destination: Path, chunk_size: int = 1024 * 1024) -> tuple[int, str]:
    """
    Persist an UploadFile to the given destination.

    Returns tuple (size_bytes, sha256_hex).
    """
    hasher = hashlib.sha256()
    size = 0

    ensure_directory(destination.parent)

    with destination.open("wb") as buffer:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break
            buffer.write(chunk)
            size += len(chunk)
            hasher.update(chunk)

    await upload.close()
    return size, hasher.hexdigest()


def sanitize_filename(name: str) -> str:
    """Basic sanitization to avoid directory traversal."""
    return Path(name).name


def allowed_content_type(content_type: str, allowed_types: Iterable[str]) -> bool:
    return any(content_type.startswith(prefix) for prefix in allowed_types)
