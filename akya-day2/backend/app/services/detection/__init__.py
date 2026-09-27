"""Pluggable detection: pick the configured detector, fall back to precomputed."""

import logging

from app.core.config import Settings
from app.services.detection.base import Detector
from app.services.detection.precomputed import PrecomputedDetector
from app.services.detection.ultralytics_detector import UltralyticsDetector

logger = logging.getLogger(__name__)

__all__ = [
    "Detector",
    "PrecomputedDetector",
    "UltralyticsDetector",
    "build_detector",
    "build_fallback_detector",
]


def build_fallback_detector(settings: Settings) -> PrecomputedDetector:
    """Precomputed detections used when the live model fails (never crash on stage)."""
    return PrecomputedDetector(settings.detections_file, settings.detect_conf_min)


def build_detector(settings: Settings) -> Detector:
    """Return the configured detector; if the model cannot load, use precomputed detections."""
    precomputed = build_fallback_detector(settings)
    if settings.detector_kind == "precomputed":
        return precomputed
    yolo = UltralyticsDetector(
        settings.detector_weights,
        settings.detect_conf_min,
        settings.detect_classes,
        device=settings.detector_device,
        imgsz=settings.detector_imgsz,
    )
    ok, detail = yolo.is_ready()
    if ok:
        return yolo
    logger.warning("ultralytics detector unavailable, using precomputed", extra={"why": detail})
    return precomputed
