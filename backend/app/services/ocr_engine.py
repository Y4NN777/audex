"""OCR engine bootstrap layer.

For now this module wraps the existing lightweight OCR implementation while
providing the structure required to plug EasyOCR (IA-006).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.pipelines import ocr as legacy_ocr


class OCREngine(Protocol):
    def extract_text(self, path: Path) -> str:
        ...


class LegacyOCREngine:
    """Current stub implementation relying on the existing Tesseract wrapper."""

    def extract_text(self, path: Path) -> str:
        return legacy_ocr.extract_text(path)


def get_ocr_engine() -> OCREngine:
    # In step IA-006 this function will instantiate the EasyOCR-backed engine.
    engine = settings.OCR_ENGINE.lower()
    if engine not in {"easyocr", "tesseract"}:
        raise ValueError(f"Unsupported OCR engine: {settings.OCR_ENGINE}")
    return LegacyOCREngine()
