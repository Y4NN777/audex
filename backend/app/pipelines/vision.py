from __future__ import annotations

from pathlib import Path

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None
    np = None

from app.pipelines.models import Observation


def detect_anomalies(image_path: Path) -> list[Observation]:
    """
    Very lightweight vision stub.

    - If OpenCV is available, computes simple brightness heuristic.
    - Otherwise produces a placeholder observation so the pipeline stays testable.
    """
    label = "general"
    try:
        if cv2 is not None and np is not None:
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError("Unable to read image.")
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            mean_brightness = float(np.mean(gray))
            severity = "high" if mean_brightness > 200 else "medium"
            confidence = min(0.99, mean_brightness / 255.0)
            return [
                Observation(
                    source_file=image_path.name,
                    label=label,
                    confidence=confidence,
                    severity=severity,
                    extra={"mean_brightness": round(mean_brightness, 2)},
                )
            ]
    except Exception:
        # fallback to default below
        pass

    return [
        Observation(
            source_file=image_path.name,
            label=label,
            confidence=0.2,
            severity="low",
            extra={"note": "vision-engine-unavailable"},
        )
    ]
