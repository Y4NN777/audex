from __future__ import annotations

from pathlib import Path

try:
    import pytesseract
except Exception:  # pragma: no cover - fallback used when lib unavailable
    pytesseract = None

from PIL import Image


def extract_text(image_path: Path) -> str:
    """Run OCR using Tesseract when available, fallback to empty string."""
    try:
        with Image.open(image_path) as image:
            if pytesseract is not None:
                return pytesseract.image_to_string(image)
            # Minimal fallback: return placeholder with dimensions
            width, height = image.size
            return f"[ocr-unavailable] image {width}x{height}px"
    except Exception:
        return ""
