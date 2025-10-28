from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.api.v1.endpoints.ingestion import get_storage_root
from app.main import app


def _make_image_bytes(width: int = 32, height: int = 32, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_create_batch_persists_files(tmp_path: Path) -> None:
    storage_dir = tmp_path / "uploads"

    app.dependency_overrides[get_storage_root] = lambda: storage_dir

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = [
            ("files", ("test.jpg", _make_image_bytes(), "image/jpeg")),
            ("files", ("notes.txt", b"Important note", "text/plain")),
        ]
        response = await client.post("/api/v1/ingestion/batches", files=files)

    app.dependency_overrides.pop(get_storage_root, None)

    assert response.status_code == status.HTTP_200_OK, response.text
    payload = response.json()
    assert "batch_id" in payload
    assert payload["stored_at"] is not None
    assert len(payload["files"]) == 2

    for file_info in payload["files"]:
        stored_path = Path(file_info["stored_path"])
        assert stored_path.exists()
        assert stored_path.read_bytes()
        assert file_info["checksum_sha256"]
        assert file_info["size_bytes"] > 0


@pytest.mark.asyncio
async def test_create_batch_rejects_unsupported_content_type(tmp_path: Path) -> None:
    storage_dir = tmp_path / "uploads"
    app.dependency_overrides[get_storage_root] = lambda: storage_dir

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = [
            ("files", ("malicious.exe", b"binary", "application/octet-stream")),
        ]
        response = await client.post("/api/v1/ingestion/batches", files=files)

    app.dependency_overrides.pop(get_storage_root, None)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"].startswith("Unsupported content type")
