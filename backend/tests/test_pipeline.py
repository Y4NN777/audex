from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.schemas.ingestion import FileMetadata
from app.services.pipeline import IngestionPipeline
from app.pipelines.models import Observation


def _create_image(path: Path, color: tuple[int, int, int] = (240, 240, 240)) -> None:
    image = Image.new("RGB", (64, 64), color)
    image.save(path, format="JPEG")


def test_pipeline_stub_processes_media(tmp_path: Path) -> None:
    img_path = tmp_path / "photo.jpg"
    text_path = tmp_path / "notes.txt"

    _create_image(img_path)
    text_path.write_text("Check extinguisher placement.", encoding="utf-8")

    pipeline = IngestionPipeline(tmp_path)

    files = [
        FileMetadata(
            filename=img_path.name,
            content_type="image/jpeg",
            size_bytes=img_path.stat().st_size,
            checksum_sha256="noop",
            stored_path=str(img_path),
            metadata=None,
        ),
        FileMetadata(
            filename=text_path.name,
            content_type="text/plain",
            size_bytes=text_path.stat().st_size,
            checksum_sha256="noop",
            stored_path=str(text_path),
            metadata=None,
        ),
    ]

    result = pipeline.run(batch_id="batch-1", files=files)

    assert result.batch_id == "batch-1"
    assert result.ocr_engine
    assert any(obs.source_file == img_path.name for obs in result.observations)
    assert len(result.ocr_texts) == 2
    assert {ocr.source_file for ocr in result.ocr_texts} == {img_path.name, text_path.name}
    for ocr in result.ocr_texts:
        assert isinstance(ocr.text, str)
        assert isinstance(ocr.warnings, list)
        assert hasattr(ocr, "confidence")
    assert result.risk is not None
    assert result.risk.batch_id == "batch-1"
    assert result.risk.total_score >= 0
    assert result.risk.breakdown
    assert result.gemini_status in {"disabled", "skipped", "no_insights", "ok"}


def test_pipeline_passes_zone_to_vision_engine(tmp_path: Path) -> None:
    img_path = tmp_path / "zone.jpg"
    _create_image(img_path)

    class RecordingVisionEngine:
        def __init__(self) -> None:
            self.calls: list[tuple[Path, str | None]] = []

        def detect(self, path: Path, zone: str | None = None):
            self.calls.append((path, zone))
            return [
                Observation(
                    source_file=path.name,
                    label="incendie",
                    confidence=0.9,
                    severity="medium",
                    bbox=(0, 0, 10, 10),
                    extra={"class_name": "fire extinguisher", "source": "yolo"},
                )
            ]

    vision_engine = RecordingVisionEngine()

    with patch("app.services.pipeline.get_vision_engine", return_value=vision_engine):
        pipeline = IngestionPipeline(tmp_path)

    files = [
        FileMetadata(
            filename=img_path.name,
            content_type="image/jpeg",
            size_bytes=img_path.stat().st_size,
            checksum_sha256="noop",
            stored_path=str(img_path),
            metadata={"zone": "Loading_Area"},
        )
    ]

    result = pipeline.run(batch_id="batch-zone", files=files)

    assert vision_engine.calls, "vision engine should be invoked"
    called_path, called_zone = vision_engine.calls[0]
    assert called_path == img_path
    assert called_zone == "Loading_Area"
    assert result.observations_local is not None
    assert len(result.observations_local) == 1
    assert result.observations_local[0].label == "incendie"
