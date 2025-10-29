from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from PIL import Image
from PIL.TiffImagePlugin import IFDRational
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.api.v1.endpoints.ingestion import get_processor, get_storage_root
from app.db.session import get_session
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

def _make_docx_bytes() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
 xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
 xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:w10="urn:schemas-microsoft-com:office:word"
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
 xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
 xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
 xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"
 xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
 mc:Ignorable="w14 wp14">
  <w:body>
    <w:p>
      <w:r>
        <w:t>Bonjour AUDEX</w:t>
      </w:r>
    </w:p>
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>""",
        )
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
async def test_create_batch_persists_files(tmp_path: Path, isolated_session: None) -> None:
    storage_dir = tmp_path / "uploads"
    processor = RecordingBatchProcessor()

    app.dependency_overrides[get_storage_root] = lambda: storage_dir
    app.dependency_overrides[get_processor] = lambda: processor

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = [
            ("files", ("test.jpg", _make_image_bytes(), "image/jpeg")),
            ("files", ("notes.txt", b"Important note", "text/plain")),
            ("files", ("rapport.docx", _make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ]
        response = await client.post("/api/v1/ingestion/batches", files=files)

    app.dependency_overrides.pop(get_storage_root, None)
    app.dependency_overrides.pop(get_processor, None)

    assert response.status_code == status.HTTP_200_OK, response.text
    payload = response.json()
    assert "batch_id" in payload
    assert payload["stored_at"] is not None
    assert len(payload["files"]) == 3
    timeline = payload.get("timeline", [])
    assert isinstance(timeline, list)
    assert timeline, "timeline should contain backend processing stages"
    assert timeline[-1]["code"] == "report:available"
    assert payload["report_url"] == f"/api/v1/ingestion/reports/{payload['batch_id']}"

    for file_info in payload["files"]:
        stored_path = Path(file_info["stored_path"])
        assert stored_path.exists()
        assert stored_path.read_bytes()
        assert file_info["checksum_sha256"]
        assert file_info["size_bytes"] > 0

    assert len(processor.calls) == 1
    recorded_batch_id, recorded_files = processor.calls[0]
    assert recorded_batch_id == payload["batch_id"]
    assert len(recorded_files) == 3


@pytest.mark.asyncio
async def test_create_batch_rejects_unsupported_content_type(tmp_path: Path, isolated_session: None) -> None:
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
async def test_create_batch_extracts_metadata(tmp_path: Path, isolated_session: None) -> None:
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
@pytest.fixture
async def isolated_session(tmp_path: Path):
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = create_async_engine(database_url, future=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async def _session_override():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = _session_override
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)
        await engine.dispose()
