from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image


def extract_image_metadata(path: Path) -> dict[str, Any]:
    """Return selected EXIF metadata if available."""
    metadata: dict[str, Any] = {}
    try:
        with Image.open(path) as img:
            exif_data = img._getexif() or {}
            if not exif_data:
                return metadata

            # Map EXIF tags to readable names
            labeled = {ExifTags.TAGS.get(tag, tag): value for tag, value in exif_data.items()}

            if "DateTimeOriginal" in labeled:
                metadata["captured_at"] = _parse_datetime(labeled["DateTimeOriginal"])
            elif "DateTime" in labeled:
                metadata["captured_at"] = _parse_datetime(labeled["DateTime"])
            if "GPSInfo" in labeled:
                gps_info = _parse_gps(labeled["GPSInfo"])
                if gps_info:
                    metadata["gps"] = gps_info
    except Exception:
        # Fallback: ignore metadata extraction failures to keep ingestion resilient
        return metadata

    return metadata


def _parse_datetime(value: Any) -> str:
    try:
        dt = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
        return dt.isoformat()
    except Exception:
        return str(value)


def _parse_gps(raw_gps: Any) -> dict[str, float] | None:
    try:
        gps_map = {ExifTags.GPSTAGS.get(key, key): raw_gps[key] for key in raw_gps}

        def _as_float(value: Any) -> float:
            if hasattr(value, "numerator") and hasattr(value, "denominator"):
                return float(value)
            if isinstance(value, tuple) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
                return value[0] / value[1] if value[1] else float(value[0])
            return float(value)

        def _convert(coord, ref) -> float:
            degrees, minutes, seconds = coord
            value = _as_float(degrees) + _as_float(minutes) / 60 + _as_float(seconds) / 3600
            if ref in ["S", "W"]:
                value *= -1
            return value

        lat = _convert(gps_map["GPSLatitude"], gps_map["GPSLatitudeRef"])
        lon = _convert(gps_map["GPSLongitude"], gps_map["GPSLongitudeRef"])
        return {"latitude": round(lat, 6), "longitude": round(lon, 6)}
    except Exception:
        return None
