"""Run the YOLO model once over every frame and cache detections for PrecomputedDetector.

The demo can then run without a GPU (or survive a CUDA failure) with the same boxes.
Uses the settings from .env (data dir, weights, device, imgsz, conf threshold).

Usage: uv run --extra detector python -m scripts.precompute_detections [--out PATH]
"""

import argparse
import json
import time
from pathlib import Path

from app.core.config import get_settings
from app.data.repository import Repository
from app.services.detection import UltralyticsDetector


def main() -> None:
    """Detect on all frames and write {image_id: [{label, confidence, bbox}]}."""
    settings = get_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--out",
        type=Path,
        default=settings.cache_dir / f"detections_{settings.detector_weights.stem}.json",
    )
    args = ap.parse_args()

    repo = Repository(settings.data_dir)
    detector = UltralyticsDetector(
        settings.detector_weights,
        settings.detect_conf_min,
        settings.detect_classes,
        device=settings.detector_device,
        imgsz=settings.detector_imgsz,
    )
    ok, detail = detector.is_ready()
    if not ok:
        raise SystemExit(f"detector not ready: {detail}")
    print(f"detector: {detail}")

    out: dict[str, list[dict[str, object]]] = {}
    started = time.perf_counter()
    for meta in repo.list_images():
        dets = detector.detect(meta.image_id, repo.image_path(meta.image_id))
        out[meta.image_id] = [
            {"label": d.label, "confidence": d.confidence, "bbox": list(d.bbox)} for d in dets
        ]
    elapsed = time.perf_counter() - started
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    total = sum(len(v) for v in out.values())
    print(f"wrote {args.out}: {len(out)} frames, {total} detections, {elapsed:.1f} s")


if __name__ == "__main__":
    main()
