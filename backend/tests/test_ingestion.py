from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from app.api.v1.endpoints.ingestion import get_processor, get_storage_root
from app.main import app


def _make_image_bytes(width: int = 32, height: int = 32, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _make_image_with_exif() -> bytes:
    image = Image.new("RGB", (32, 32), (0, 128, 255))
    exif = Image.Exif()
    exif[36867] = "2024:01:02 12:34:56"
    exif[34853] = {
        1: "N",
        2: (IFDRational(12, 1), IFDRational(34, 1), IFDRational(0, 1)),
        3: "E",
        4: (IFDRational(56, 1), IFDRational(7, 1), IFDRational(0, 1)),
    }
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


class RecordingBatchProcessor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[dict]]] = []

    def enqueue(self, batch_id: str, files) -> None:
        payload = []
        for file in files:
            if hasattr(file, "model_dump"):
                payload.append(file.model_dump())
            else:
                payload.append(file)
        self.calls.append((batch_id, payload))


@pytest.mark.asyncio
async def test_create_batch_persists_files(tmp_path: Path) -> None:
    storage_dir = tmp_path / "uploads"
    processor = RecordingBatchProcessor()

    app.dependency_overrides[get_storage_root] = lambda: storage_dir
    app.dependency_overrides[get_processor] = lambda: processor

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = [
            ("files", ("test.jpg", _make_image_bytes(), "image/jpeg")),
            ("files", ("notes.txt", b"Important note", "text/plain")),
        ]
        response = await client.post("/api/v1/ingestion/batches", files=files)

    app.dependency_overrides.pop(get_storage_root, None)
    app.dependency_overrides.pop(get_processor, None)

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

    assert len(processor.calls) == 1
    recorded_batch_id, recorded_files = processor.calls[0]
    assert recorded_batch_id == payload["batch_id"]
    assert len(recorded_files) == 2


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


@pytest.mark.asyncio
async def test_create_batch_extracts_metadata(tmp_path: Path) -> None:
    storage_dir = tmp_path / "uploads"
    processor = RecordingBatchProcessor()

    app.dependency_overrides[get_storage_root] = lambda: storage_dir
    app.dependency_overrides[get_processor] = lambda: processor

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = [
            ("files", ("exif.jpg", _make_image_with_exif(), "image/jpeg")),
        ]
        response = await client.post("/api/v1/ingestion/batches", files=files)

    app.dependency_overrides.pop(get_storage_root, None)
    app.dependency_overrides.pop(get_processor, None)

    assert response.status_code == status.HTTP_200_OK
    file_info = response.json()["files"][0]
    metadata = file_info["metadata"]
    assert metadata is not None
    assert metadata["captured_at"].startswith("2024-01-02T12:34:56")
    gps = metadata["gps"]
    assert pytest.approx(gps["latitude"], 0.01) == 12.5666  # approx 12 deg 34 min
    assert pytest.approx(gps["longitude"], 0.01) == 56.1166
