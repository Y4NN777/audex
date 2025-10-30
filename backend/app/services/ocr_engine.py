"""OCR engine bootstrap layer.

For now this module wraps the existing lightweight OCR implementation while
providing the structure required to plug EasyOCR (IA-006).
"""
from __future__ import annotations

import threading
from logging import getLogger
from pathlib import Path
from typing import Protocol, Sequence

from app.core.config import settings
from app.pipelines import ocr as legacy_ocr

try:  # pragma: no cover - optional dependency, exercised via integration tests
    import easyocr  # type: ignore
except Exception:  # noqa: BLE001 - importing heavy lib may fail without deps
    easyocr = None

logger = getLogger(__name__)


class OCREngine(Protocol):
    engine_id: str

    def extract_text(self, path: Path) -> str:
        ...


class LegacyOCREngine:
    """Wrapper around the historical OCR module (pytesseract-based)."""

    engine_id = "tesseract"

    def extract_text(self, path: Path) -> str:
        return legacy_ocr.extract_text(path)


class EasyOCREngine:
    """Lightweight adapter around EasyOCR with lazy model loading."""

    engine_id = "easyocr"

    def __init__(self, languages: Sequence[str]) -> None:
        self._languages = list(languages) or ["en"]
        self._reader: "easyocr.Reader | None" = None  # type: ignore[name-defined]
        self._lock = threading.Lock()
        self._initialisation_failed = False

    @staticmethod
    def is_available() -> bool:
        return easyocr is not None

    def _get_reader(self) -> "easyocr.Reader":  # type: ignore[name-defined]
        if self._reader is not None:
            return self._reader
        if self._initialisation_failed:
            raise RuntimeError("EasyOCR initialisation previously failed.")

        if easyocr is None:
            raise RuntimeError("EasyOCR is not available in the current environment.")

        with self._lock:
            if self._reader is None:
                logger.info(
                    "Initialising EasyOCR reader for languages %s (gpu=off).",
                    ", ".join(self._languages),
                )
                try:
                    self._reader = easyocr.Reader(  # type: ignore[attr-defined]
                        self._languages,
                        gpu=False,
                        download_enabled=False,
                    )
                except Exception as exc:  # noqa: BLE001
                    self._initialisation_failed = True
                    logger.warning(
                        "Unable to initialise EasyOCR (languages=%s): %s",
                        ", ".join(self._languages),
                        exc,
                    )
                    raise
        return self._reader

    def extract_text(self, path: Path) -> str:
        try:
            reader = self._get_reader()
            lines = reader.readtext(str(path), detail=0)  # type: ignore[assignment]
            return "\n".join(line.strip() for line in lines if isinstance(line, str) and line.strip())
        except Exception as exc:  # noqa: BLE001
            logger.warning("EasyOCR failed on %s: %s. Falling back to legacy OCR.", path, exc)
            return legacy_ocr.extract_text(path)


def get_ocr_engine() -> OCREngine:
    engine = settings.OCR_ENGINE.lower().strip()
    if engine == "easyocr":
        if EasyOCREngine.is_available():
            return EasyOCREngine(settings.OCR_LANGUAGES)
        logger.warning("EasyOCR requested but unavailable; falling back to legacy OCR.")
        return LegacyOCREngine()
    if engine == "tesseract":
        return LegacyOCREngine()
    raise ValueError(f"Unsupported OCR engine: {settings.OCR_ENGINE}")
