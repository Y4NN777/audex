from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from app.services.vision_engine import YOLOVisionEngine


def _create_image(path: Path, color: tuple[int, int, int] = (255, 0, 0)) -> None:
    image = Image.new("RGB", (32, 32), color)
    image.save(path, format="JPEG")


@patch("app.services.vision_engine.YOLO")
def test_yolo_engine_converts_boxes_to_observations(mock_yolo, tmp_path: Path) -> None:
    image_path = tmp_path / "frame.jpg"
    _create_image(image_path)

    mock_model = MagicMock()
    mock_yolo.return_value = mock_model

    fake_box = MagicMock()
    fake_box.cls.item.return_value = 0
    fake_box.conf.item.return_value = 0.92
    fake_box.xyxy.__getitem__.return_value.tolist.return_value = [0, 0, 32, 32]

    fake_boxes = MagicMock()
    fake_boxes.data = [fake_box]
    fake_boxes.__iter__.return_value = [fake_box]

    fake_result = MagicMock()
    fake_result.names = {0: "fire extinguisher"}
    fake_result.boxes = fake_boxes

    mock_model.predict.return_value = [fake_result]

    engine = YOLOVisionEngine(model_path=str(image_path))

    with patch.object(engine, "_load_model", return_value=mock_model):
        observations = engine.detect(image_path, zone="corridor")

    yolo_observations = [obs for obs in observations if obs.extra.get("source") == "yolo"]
    assert len(yolo_observations) == 1
    obs = yolo_observations[0]
    assert obs.label == "incendie"
    assert obs.severity == "high"
    assert obs.extra["class_name"] == "fire extinguisher"
