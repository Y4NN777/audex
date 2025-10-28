from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Observation:
    """Single anomaly detected by the pipeline."""

    source_file: str
    label: str
    confidence: float
    severity: str = "medium"
    bbox: tuple[int, int, int, int] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OCRResult:
    """Raw OCR extraction per file."""

    source_file: str
    text: str


@dataclass(slots=True)
class PipelineResult:
    batch_id: str
    observations: list[Observation]
    ocr_texts: list[OCRResult]
