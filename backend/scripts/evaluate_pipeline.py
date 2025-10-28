#!/usr/bin/env python3
"""Quick evaluation harness for the AUDEX ingestion pipeline.

Usage:
    python backend/scripts/evaluate_pipeline.py --batch-id demo --dataset path/to/folder
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.schemas.ingestion import FileMetadata
from app.services.pipeline import IngestionPipeline


def build_metadata(dataset: Path) -> list[FileMetadata]:
    files: list[FileMetadata] = []
    for path in dataset.iterdir():
        if not path.is_file():
            continue
        content_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".txt": "text/plain",
            ".pdf": "application/pdf",
        }.get(path.suffix.lower(), "application/octet-stream")

        files.append(
            FileMetadata(
                filename=path.name,
                content_type=content_type,
                size_bytes=path.stat().st_size,
                checksum_sha256="",
                stored_path=str(path),
                metadata=None,
            )
        )
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate AUDEX ingestion pipeline on a dataset folder.")
    parser.add_argument("--batch-id", default="demo-batch")
    parser.add_argument("--dataset", required=True, type=Path, help="Directory containing sample files.")
    args = parser.parse_args()

    if not args.dataset.exists():
        raise SystemExit(f"Dataset folder '{args.dataset}' not found.")

    pipeline = IngestionPipeline(args.dataset)
    result = pipeline.run(batch_id=args.batch_id, files=build_metadata(args.dataset))

    print(f"Batch: {result.batch_id}")
    print(f"Observations: {len(result.observations)}")
    for obs in result.observations:
        print(f" - {obs.source_file} :: {obs.label} ({obs.severity}) confidence={obs.confidence:.2f}")
    print("\nOCR snippets:")
    for ocr in result.ocr_texts:
        snippet = (ocr.text[:120] + "...") if len(ocr.text) > 120 else ocr.text
        print(f" - {ocr.source_file}: {snippet}")


if __name__ == "__main__":
    main()
