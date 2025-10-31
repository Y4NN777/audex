from __future__ import annotations

import json
import asyncio
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient, Response
from PIL import Image
from PIL.TiffImagePlugin import IFDRational
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.api.v1.endpoints.ingestion import get_processor, get_storage_root
from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.pipelines.models import Observation
from app.services.advanced_analyzer import GeminiAnalysisResult
from app.services.report_summary import SummaryResult


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


def _make_pdf_bytes() -> bytes:
    fitz_module = pytest.importorskip("fitz")
    document = fitz_module.open()
    page = document.new_page()
    page.insert_text((72, 72), "Extincteur manquant au poste A", fontsize=12)
    buffer = BytesIO()
    document.save(buffer)
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


async def _wait_for_status(
    client: AsyncClient,
    batch_id: str,
    expected: str = "completed",
    timeout: float = 15.0,
    poll_interval: float = 0.1,
) -> Response:
    deadline = asyncio.get_event_loop().time() + timeout
    last_response: Response | None = None
    while asyncio.get_event_loop().time() < deadline:
        detail_response = await client.get(f"/api/v1/ingestion/batches/{batch_id}")
        last_response = detail_response
        if detail_response.status_code == status.HTTP_200_OK:
            payload = detail_response.json()
            if payload.get("status") == expected:
                return detail_response
        await asyncio.sleep(poll_interval)
    body = last_response.json() if last_response is not None else None
    raise AssertionError(
        f"Batch {batch_id} did not reach status {expected!r} within {timeout} seconds. Last payload: {body}"
    )


@pytest.mark.asyncio
async def test_create_batch_persists_files(tmp_path: Path, isolated_session: None) -> None:
    storage_dir = tmp_path / "uploads"
    processor = RecordingBatchProcessor()

    app.dependency_overrides[get_storage_root] = lambda: storage_dir
    app.dependency_overrides[get_processor] = lambda: processor

    summary_result = SummaryResult(
        status="ok",
        text="Synthèse test",
        findings=["finding-a"],
        recommendations=["rec-a"],
        warnings=[],
        source="google-gemini",
        prompt_hash="s" * 64,
        response_hash="r" * 64,
        duration_ms=1200,
    )

    with patch("app.services.pipeline.ReportSummaryService.generate", return_value=summary_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            files = [
                ("files", ("test.jpg", _make_image_bytes(), "image/jpeg")),
                ("files", ("notes.txt", b"Important note", "text/plain")),
                ("files", ("rapport.docx", _make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
                ("files", ("synthese.pdf", _make_pdf_bytes(), "application/pdf")),
            ]
            response = await client.post("/api/v1/ingestion/batches", files=files)
            payload = response.json()
            batch_id = payload["batch_id"]
            detail_response = await _wait_for_status(client, batch_id)
            detail = detail_response.json()

    app.dependency_overrides.pop(get_storage_root, None)
    app.dependency_overrides.pop(get_processor, None)

    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    assert payload["status"] == "processing"
    assert payload.get("timeline") == []

    assert detail["status"] == "completed"
    assert len(detail["files"]) == 4
    assert detail["gemini_model"] == settings.GEMINI_MODEL
    ocr_texts = detail["ocr_texts"]
    assert ocr_texts is not None
    assert isinstance(ocr_texts, list)
    assert ocr_texts, "ocr_texts should contain OCR outputs"
    assert detail["gemini_status"] in {"disabled", "skipped", "no_insights", "ok"}
    assert detail["gemini_summary"] is None or isinstance(detail["gemini_summary"], str)
    prompt_hash = detail["gemini_prompt_hash"]
    if prompt_hash is not None:
        assert isinstance(prompt_hash, str)
        assert len(prompt_hash) == 64
    risk_score = detail["risk_score"]
    assert risk_score is not None
    assert "total_score" in risk_score
    assert isinstance(risk_score["breakdown"], list)
    ocr_by_filename = {entry["filename"]: entry for entry in ocr_texts}
    assert set(ocr_by_filename.keys()) == {"test.jpg", "notes.txt", "rapport.docx", "synthese.pdf"}
    for entry in ocr_by_filename.values():
        assert "confidence" in entry
        assert "warnings" in entry
        assert "error" in entry
    assert "Bonjour AUDEX" in ocr_by_filename["rapport.docx"]["content"]
    if ocr_by_filename["synthese.pdf"]["content"]:
        assert "Extincteur" in ocr_by_filename["synthese.pdf"]["content"]
    timeline = detail.get("timeline", [])
    assert isinstance(timeline, list)
    assert timeline, "timeline should contain backend processing stages"
    assert timeline[-1]["code"] == "report:available"
    assert detail["report_url"] == f"/api/v1/ingestion/reports/{detail['batch_id']}"
    assert "observations" in detail

    for file_info in detail["files"]:
        stored_path = Path(file_info["stored_path"])
        assert stored_path.exists()
        assert stored_path.read_bytes()
        assert file_info["checksum_sha256"]
        assert file_info["size_bytes"] > 0

    assert len(processor.calls) == 1
    recorded_batch_id, recorded_files = processor.calls[0]
    assert recorded_batch_id == detail["batch_id"]
    assert len(recorded_files) == 4
    summary_payload = detail.get("summary")
    assert summary_payload is not None
    assert summary_payload["status"] == "ok"
    assert summary_payload["text"] == "Synthèse test"
    assert summary_payload["findings"] == ["finding-a"]
    assert summary_payload["recommendations"] == ["rec-a"]


@pytest.mark.asyncio
async def test_get_batch_returns_persisted_metadata_and_timeline(tmp_path: Path, isolated_session: None) -> None:
    storage_dir = tmp_path / "uploads"
    processor = RecordingBatchProcessor()

    app.dependency_overrides[get_storage_root] = lambda: storage_dir
    app.dependency_overrides[get_processor] = lambda: processor

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = [
            ("files", ("exif.jpg", _make_image_with_exif(), "image/jpeg")),
            ("files", ("notes.txt", b"note", "text/plain")),
        ]
        create_response = await client.post("/api/v1/ingestion/batches", files=files)
        batch_id = create_response.json()["batch_id"]

        detail_response = await _wait_for_status(client, batch_id)

    app.dependency_overrides.pop(get_storage_root, None)
    app.dependency_overrides.pop(get_processor, None)

    assert detail_response.status_code == status.HTTP_200_OK, detail_response.text
    detail = detail_response.json()
    assert detail["status"] == "completed"
    assert {file["filename"] for file in detail["files"]} == {"exif.jpg", "notes.txt"}
    assert "observations" in detail
    observations = detail["observations"]
    assert all(obs["source"] in {"local", "gemini"} for obs in observations)
    assert {entry["filename"] for entry in detail["ocr_texts"]} == {"exif.jpg", "notes.txt"}
    for entry in detail["ocr_texts"]:
        assert "confidence" in entry
        assert "warnings" in entry
        assert "error" in entry
    exif_entry = next(file for file in detail["files"] if file["filename"] == "exif.jpg")
    assert exif_entry["metadata"] is not None
    codes = [event["code"] for event in detail["timeline"]]
    assert "ingestion:received" in codes
    assert "report:available" in codes
    assert detail["gemini_status"] in {"disabled", "skipped", "no_insights", "ok"}
    assert detail["gemini_model"] == settings.GEMINI_MODEL
    assert detail["gemini_summary"] is None or isinstance(detail["gemini_summary"], str)
    prompt_hash = detail["gemini_prompt_hash"]
    if prompt_hash is not None:
        assert isinstance(prompt_hash, str)
        assert len(prompt_hash) == 64
    risk_detail = detail["risk_score"]
    assert risk_detail is not None
    assert "total_score" in risk_detail
    assert isinstance(risk_detail["breakdown"], list)


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
        batch_id = response.json()["batch_id"]
        detail_response = await _wait_for_status(client, batch_id)
        detail = detail_response.json()

    app.dependency_overrides.pop(get_storage_root, None)
    app.dependency_overrides.pop(get_processor, None)

    assert response.status_code == status.HTTP_202_ACCEPTED
    file_info = detail["files"][0]
    metadata = file_info["metadata"]
    assert metadata is not None
    assert metadata["captured_at"].startswith("2024-01-02T12:34:56")
    gps = metadata["gps"]
    assert pytest.approx(gps["latitude"], 0.01) == 12.5666  # approx 12 deg 34 min
    assert pytest.approx(gps["longitude"], 0.01) == 56.1166
    ocr_texts = detail["ocr_texts"]
    assert ocr_texts and ocr_texts[0]["engine"]
    assert "confidence" in ocr_texts[0]
    assert "warnings" in ocr_texts[0]
    response_body = detail
    assert response_body["gemini_status"] in {"disabled", "skipped", "no_insights", "ok"}
    assert response_body["gemini_model"] == settings.GEMINI_MODEL
    assert response_body["gemini_summary"] is None or isinstance(response_body["gemini_summary"], str)
    prompt_hash = response_body["gemini_prompt_hash"]
    if prompt_hash is not None:
        assert isinstance(prompt_hash, str)
        assert len(prompt_hash) == 64
    risk_snapshot = response_body["risk_score"]
    assert risk_snapshot is not None
    assert "total_score" in risk_snapshot


@pytest.mark.asyncio
async def test_manual_gemini_analysis_endpoint(tmp_path: Path, isolated_session: None) -> None:
    storage_dir = tmp_path / "uploads"
    processor = RecordingBatchProcessor()

    app.dependency_overrides[get_storage_root] = lambda: storage_dir
    app.dependency_overrides[get_processor] = lambda: processor

    summary_result = SummaryResult(
        status="ok",
        text="Synthèse test",
        findings=["finding-a"],
        recommendations=["rec-a"],
        warnings=[],
        source="google-gemini",
        prompt_hash="s" * 64,
        response_hash="r" * 64,
        duration_ms=1200,
    )

    with patch("app.services.pipeline.ReportSummaryService.generate", return_value=summary_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            files = [
                ("files", ("exif.jpg", _make_image_with_exif(), "image/jpeg")),
                ("files", ("notes.txt", b"note", "text/plain")),
            ]
            create_response = await client.post("/api/v1/ingestion/batches", files=files)
            batch_id = create_response.json()["batch_id"]

            fake_result = GeminiAnalysisResult(
                observations=[
                    Observation(
                        source_file="exif.jpg",
                        label="security_fence_breach",
                        confidence=0.92,
                        severity="high",
                        extra={"source": "gemini", "category": "access_control"},
                    )
                ],
                summary=json.dumps({"observations": [{"label": "security_fence_breach"}], "warnings": []}),
                status="ok",
                warnings=["gemini-warning"],
                prompt_hash="a" * 64,
                duration_ms=512,
                payloads=[{"security_level": "medium"}],
                model="gemini-2.0-flash-exp",
                provider="google-gemini",
                prompt_version="schema-1.4-bfa",
            )

            with patch("app.api.v1.endpoints.ingestion.AdvancedAnalyzer") as analyzer_mock:
                analyzer_instance = analyzer_mock.return_value
                analyzer_instance.enabled = True
                analyzer_instance.api_key = "test-key"
                analyzer_instance.model = "gemini-2.0-flash-exp"
                analyzer_instance.analyze.return_value = fake_result

                post_response = await client.post(
                    f"/api/v1/ingestion/batches/{batch_id}/analysis",
                    json={"requested_by": "qa-tester"},
                )

                post_status = post_response.status_code
                analysis_data = post_response.json()

            history_response = await client.get(
                f"/api/v1/ingestion/batches/{batch_id}/analysis",
                params={"include_history": "true"},
            )
            history_status = history_response.status_code
            history_payload = history_response.json()

            detail_response = await _wait_for_status(client, batch_id)
            detail_status = detail_response.status_code
            detail_body = detail_response.json()

        assert post_status == status.HTTP_200_OK, post_response.text
        assert analysis_data["status"] == "ok"
        assert analysis_data["requested_by"] == "qa-tester"
        assert analysis_data["prompt_hash"] == "a" * 64
        assert analysis_data["observations"][0]["label"] == "security_fence_breach"

        assert history_status == status.HTTP_200_OK
        assert history_payload["latest"]["status"] == "ok"
        assert history_payload["history"]
        manual_entries = [
            item
            for item in history_payload["history"]
            if item.get("requested_by") == "qa-tester" and item.get("status") == "ok"
        ]
        assert manual_entries, "Manual Gemini analysis should be present in history"

        assert detail_status == status.HTTP_200_OK
        assert detail_body["gemini_status"] == "ok"
        assert detail_body["gemini_prompt_hash"] == "a" * 64
        assert detail_body["risk_score"] is not None

    app.dependency_overrides.pop(get_storage_root, None)
    app.dependency_overrides.pop(get_processor, None)


@pytest_asyncio.fixture
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
