"""Vision engine bootstrap layer.

Provides a pluggable interface to the vision pipeline. Currently wraps the
legacy brightness heuristic while the YOLO integration is prepared (IA-006).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Protocol

from app.core.config import settings
from app.pipelines import vision as legacy_vision
from app.pipelines.models import Observation


class VisionEngine(Protocol):
    def detect(self, path: Path) -> List[Observation]:
        ...


class LegacyVisionEngine:
    def detect(self, path: Path) -> List[Observation]:
        return legacy_vision.detect_anomalies(path)


def get_vision_engine() -> VisionEngine:
    model = settings.VISION_MODEL_PATH
    # Placeholder: real YOLO loader viendra lors de IA-006.
    if not model:
        raise ValueError("VISION_MODEL_PATH must be configured")
    return LegacyVisionEngine()
