"""Ultralytics (YOLO .pt) adapter. `ultralytics` is an optional extra and imported lazily.

FP16 is deliberately not used: on GTX 16xx cards (our dev GPU) half precision returned no boxes
and ran ~3x slower than FP32.
"""

import logging
from pathlib import Path
from typing import Any

from app.core.errors import DetectorError
from app.domain.detection import Detection
from app.services.detection.base import make_detection

logger = logging.getLogger(__name__)


def _resolve_device(device: str) -> str | int:
    """ "auto" -> first CUDA GPU if available, else CPU; otherwise pass through ("cpu", "0")."""
    if device != "auto":
        return int(device) if device.isdigit() else device
    try:
        import torch
    except ImportError:
        return "cpu"
    return 0 if torch.cuda.is_available() else "cpu"


class UltralyticsDetector:
    """Runs a YOLO model from a `.pt` file; keeps only vehicle classes above `conf_min`."""

    name = "ultralytics"

    def __init__(
        self,
        weights: Path,
        conf_min: float,
        classes: list[str],
        device: str = "auto",
        imgsz: int | None = None,
    ) -> None:
        self._weights = weights
        self._conf_min = conf_min
        self._classes = {c.lower() for c in classes}
        self._device_setting = device
        self._imgsz = imgsz
        self._device: str | int = "cpu"
        self._model: Any = None

    def _predict_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"conf": self._conf_min, "device": self._device, "verbose": False}
        if self._imgsz:
            kwargs["imgsz"] = self._imgsz
        return kwargs

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        if not self._weights.is_file():
            raise DetectorError(f"weights not found: {self._weights.name}")
        try:
            import numpy as np
            from ultralytics import YOLO
        except ImportError as exc:
            raise DetectorError("ultralytics not installed (uv sync --extra detector)") from exc
        self._device = _resolve_device(self._device_setting)
        model = YOLO(str(self._weights))
        # Warm-up so the first live analysis does not pay CUDA init (~1-2 s).
        model.predict(np.zeros((540, 960, 3), dtype=np.uint8), **self._predict_kwargs())
        self._model = model
        logger.info(
            "detector loaded",
            extra={"weights": self._weights.name, "device": self._device, "imgsz": self._imgsz},
        )
        return model

    def is_ready(self) -> tuple[bool, str]:
        """Ready when weights load; loading happens once."""
        try:
            model = self._load()
        except DetectorError as exc:
            return False, exc.detail
        device = "GPU" if self._device != "cpu" else "CPU"
        return True, f"{self._weights.name} · {len(model.names)} classes · {device}"

    def detect(self, image_id: str, image_path: Path | None) -> list[Detection]:
        """Run inference on one image; returns xywh pixel boxes."""
        if image_path is None:
            raise DetectorError(f"image file for {image_id} not found")
        model = self._load()
        try:
            result = model.predict(str(image_path), **self._predict_kwargs())[0]
        except Exception as exc:  # torch/CUDA errors are untyped; surface as DetectorError
            raise DetectorError(f"inference failed: {exc}") from exc
        names: dict[int, str] = model.names
        model_classes = {n.lower() for n in names.values()}
        # A custom model may use other class names (e.g. "vehicle"); then keep everything.
        filter_classes = bool(self._classes & model_classes)
        if not filter_classes:
            logger.warning(
                "detector classes do not overlap config; keeping all",
                extra={"image_id": image_id, "model_classes": sorted(model_classes)},
            )

        detections: list[Detection] = []
        for xyxy, cls, conf in zip(
            result.boxes.xyxy.tolist(),
            result.boxes.cls.tolist(),
            result.boxes.conf.tolist(),
            strict=True,
        ):
            label = names[int(cls)].lower()
            if filter_classes and label not in self._classes:
                continue
            x1, y1, x2, y2 = xyxy
            bbox = (round(x1), round(y1), round(x2 - x1), round(y2 - y1))
            detections.append(make_detection(len(detections) + 1, label, float(conf), bbox))
        return detections
