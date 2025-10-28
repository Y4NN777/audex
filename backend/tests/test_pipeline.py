from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.schemas.ingestion import FileMetadata
from app.services.pipeline import IngestionPipeline


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
    assert any(obs.source_file == img_path.name for obs in result.observations)
    assert len(result.ocr_texts) == 2
    assert {ocr.source_file for ocr in result.ocr_texts} == {img_path.name, text_path.name}
