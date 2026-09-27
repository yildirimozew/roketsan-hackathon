"""Detector that reads detections from a JSON file (fallback and demo-safe path).

File format (our own, written by precompute or by hand):
    {"img_000860": [{"label": "truck", "confidence": 0.87, "bbox": [727, 284, 58, 34]}]}
"""

from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from app.domain.detection import Detection
from app.services.detection.base import make_detection


class _RawDetection(BaseModel):
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, w, h in pixels


_FILE_ADAPTER = TypeAdapter(dict[str, list[_RawDetection]])


class PrecomputedDetector:
    """Serves detections from a JSON file keyed by image id."""

    name = "precomputed"

    def __init__(self, detections_file: Path, conf_min: float) -> None:
        self._file = detections_file
        self._conf_min = conf_min
        self._data: dict[str, list[_RawDetection]] = {}
        if detections_file.is_file():
            self._data = _FILE_ADAPTER.validate_json(detections_file.read_bytes())

    def is_ready(self) -> tuple[bool, str]:
        """Ready when the JSON file exists and has entries."""
        if not self._data:
            return False, f"no precomputed detections at {self._file.name}"
        return True, f"{len(self._data)} frames precomputed"

    def detect(self, image_id: str, image_path: Path | None) -> list[Detection]:
        """Return stored detections for `image_id` above the confidence threshold."""
        kept = [r for r in self._data.get(image_id, []) if r.confidence >= self._conf_min]
        return [make_detection(i + 1, r.label, r.confidence, r.bbox) for i, r in enumerate(kept)]
