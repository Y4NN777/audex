"""Vision engine bootstrap layer.

Provides a pluggable interface to the vision pipeline. The default engine now
relies on YOLOv8n when available, with graceful fallback towards the legacy heuristic
if the model is not accessible (offline mode / missing dependencies).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Iterable, List, Protocol

try:  # pragma: no cover - ultralytics n'est pas installé durant les tests.
    from ultralytics import YOLO  # type: ignore
except Exception:  # pragma: no cover
    YOLO = None  # type: ignore[assignment]

try:  # pragma: no cover
    import torch  # type: ignore
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]

from app.core.config import settings
from app.pipelines import vision as legacy_vision
from app.pipelines.models import Observation
from app.services import vision_rules


class VisionEngine(Protocol):
    def detect(self, path: Path, zone: str | None = None) -> List[Observation]:
        ...


class LegacyVisionEngine:
    """Fallback historique basé sur les heuristiques simples."""

    def detect(self, path: Path, zone: str | None = None) -> List[Observation]:
        return legacy_vision.detect_anomalies(path)


class YOLOVisionEngine:
    """Moteur YOLOv8n + règles métiers AUDEX."""

    def __init__(self, model_path: str, confidence: float = 0.25) -> None:
        if YOLO is None:
            raise RuntimeError("Ultralytics YOLO n'est pas disponible.")

        self._model_path = model_path
        self._confidence = confidence
        self._lock = threading.Lock()
        self._model: "YOLO | None" = None  # type: ignore[name-defined]
        self._initialization_failed = False

    def _load_model(self) -> "YOLO":  # type: ignore[name-defined]
        if self._model is not None:
            return self._model
        if self._initialization_failed:
            raise RuntimeError("YOLO model initialization previously failed.")

        with self._lock:
            if self._model is None:
                weights_path = Path(self._model_path)
                if not weights_path.exists():
                    self._initialization_failed = True
                    raise FileNotFoundError(f"YOLO weights not found at {self._model_path!r}")
                self._model = YOLO(str(weights_path))  # type: ignore[call-arg]
                if torch is not None:
                    try:
                        self._model.to("cpu")  # type: ignore[call-arg]
                    except Exception:  # pragma: no cover - device optionnel
                        pass
        return self._model

    def detect(self, path: Path, zone: str | None = None) -> List[Observation]:
        observations: list[Observation] = []
        try:
            model = self._load_model()
            results = model.predict(  # type: ignore[call-arg]
                source=str(path),
                conf=self._confidence,
                verbose=False,
                device="cpu",
            )

            for result in results:
                names = result.names
                boxes = getattr(result, "boxes", None)
                if boxes is None or boxes.data is None:
                    continue

                for box in boxes:
                    cls_id_tensor = getattr(box, "cls", None)
                    conf_tensor = getattr(box, "conf", None)
                    xyxy_tensor = getattr(box, "xyxy", None)

                    if cls_id_tensor is None or conf_tensor is None or xyxy_tensor is None:
                        continue

                    class_index = int(cls_id_tensor.item())
                    class_name = str(names.get(class_index, f"class_{class_index}"))
                    confidence = float(conf_tensor.item())
                    bbox_xyxy = [float(v) for v in xyxy_tensor[0].tolist()]  # type: ignore[index]

                    mapping = vision_rules.map_class(class_name, confidence, zone=zone)
                    if mapping is None:
                        continue

                    category, severity = mapping

                    zone_norm = zone.strip().lower() if isinstance(zone, str) and zone.strip() else None

                    observation = Observation(
                        source_file=path.name,
                        label=category,
                        confidence=confidence,
                        severity=severity,
                        bbox=(
                            int(bbox_xyxy[0]),
                            int(bbox_xyxy[1]),
                            int(bbox_xyxy[2]),
                            int(bbox_xyxy[3]),
                        ),
                        extra={
                            "class_name": class_name,
                            "source": "yolo",
                            "zone": zone_norm,
                        },
                    )
                    observations.append(observation)

        except Exception:
            # Retour au legacy en cas d'échec (modèle manquant, erreur I/O, etc.)
            observations.extend(legacy_vision.detect_anomalies(path))

        # Ajouter les heuristiques qualité (luminosité/flou), même en mode fallback.
        observations.extend(vision_rules.apply_quality_checks(path, zone=zone))

        return observations


def get_vision_engine() -> VisionEngine:
    model_path = settings.VISION_MODEL_PATH
    if not model_path:
        raise ValueError("VISION_MODEL_PATH must be configuré")

    if YOLO is None or not settings.VISION_ENABLE_YOLO:
        return LegacyVisionEngine()

    try:
        return YOLOVisionEngine(model_path=model_path)
    except Exception:
        return LegacyVisionEngine()
