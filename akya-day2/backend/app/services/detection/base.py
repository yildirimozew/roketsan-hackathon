"""Detector protocol and shared helpers."""

from pathlib import Path
from typing import Protocol

from app.domain.detection import Detection


class Detector(Protocol):
    """Anything that turns one frame into vehicle detections."""

    name: str

    def is_ready(self) -> tuple[bool, str]:
        """Return (available, human-readable detail) for the health endpoint."""
        ...

    def detect(self, image_id: str, image_path: Path | None) -> list[Detection]:
        """Detect vehicles in one frame; pixel units, no geo fields filled.

        `image_path` is None when the image file is missing (precomputed detections still work).
        """
        ...


def make_detection(
    index: int, label: str, confidence: float, bbox: tuple[int, int, int, int]
) -> Detection:
    """Build a `Detection` with id `DET-<index>` and its pixel center from an xywh bbox."""
    x, y, w, h = bbox
    return Detection(
        id=f"DET-{index}",
        label=label,
        confidence=round(confidence, 4),
        bbox=bbox,
        center_px=(x + w / 2, y + h / 2),
    )
