#!/usr/bin/env python3
"""Pré-télécharge les modèles EasyOCR nécessaires pour l'exécution offline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download EasyOCR detection/recognition models ahead of time."
    )
    parser.add_argument(
        "--languages",
        "-l",
        nargs="+",
        help="Lang codes to warm up (defaults to OCR_LANGUAGES from settings).",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Warm-up with GPU enabled (defaults to CPU).",
    )
    return parser.parse_args()


def _sanitize_languages(languages: Iterable[str]) -> list[str]:
    sanitized: list[str] = []
    for item in languages:
        item = item.strip()
        if item:
            sanitized.append(item)
    return sanitized or ["en"]


def warmup(languages: list[str], gpu: bool = False) -> None:
    try:
        import easyocr  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("EasyOCR is not installed in the current environment.") from exc

    from app.core.config import settings

    languages = languages or settings.OCR_LANGUAGES
    languages = _sanitize_languages(languages)

    print(f"[warmup] Initialising EasyOCR for languages: {', '.join(languages)} (gpu={gpu})")
    reader = easyocr.Reader(  # type: ignore[attr-defined]
        languages,
        gpu=gpu,
        download_enabled=True,
        verbose=True,
    )
    # Running a dummy inference ensures recognition models are touched as well.
    try:
        import numpy as np

        dummy = np.zeros((32, 32, 3), dtype=np.uint8)
        reader.readtext(dummy)  # type: ignore[attr-defined]
    except Exception:
        # Any failure here is non-blocking; the important part is the download.
        pass

    model_dir = Path.home() / ".EasyOCR"
    print(f"[warmup] Completed. Models cached under: {model_dir}")


def main() -> int:
    args = _parse_args()
    try:
        warmup(args.languages or [], gpu=args.gpu)
    except Exception as exc:  # noqa: BLE001
        print(f"[warmup] Failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
