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
    confidence: float | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class PipelineResult:
    batch_id: str
    observations: list[Observation]
    ocr_texts: list[OCRResult]
    ocr_engine: str | None = None
    risk: "RiskScore | None" = None


@dataclass(slots=True)
class RiskBreakdown:
    label: str
    severity: str
    count: int
    score: float


@dataclass(slots=True)
class RiskScore:
    batch_id: str
    total_score: float
    normalized_score: float
    breakdown: list[RiskBreakdown]
