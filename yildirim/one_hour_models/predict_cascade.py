#!/usr/bin/env python3
"""Run Cascade R-CNN inference and save competition-style box predictions."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from mmengine.config import Config
from mmdet.apis import inference_detector, init_detector


CLASS_NAMES = ("car", "van", "truck", "bus")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-ids", type=Path)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--score-threshold", type=float, default=0.001)
    return parser.parse_args()


def requested_images(images_dir: Path, manifest: Path | None) -> list[Path]:
    if manifest is None:
        return sorted(
            path for path in images_dir.iterdir()
            if path.suffix.lower() in IMAGE_SUFFIXES
        )
    ids = manifest.read_text().split()
    by_stem = {
        path.stem: path for path in images_dir.iterdir()
        if path.suffix.lower() in IMAGE_SUFFIXES
    }
    missing = [image_id for image_id in ids if image_id not in by_stem]
    if missing:
        raise FileNotFoundError(f"missing {len(missing)} requested images; first: {missing[:5]}")
    return [by_stem[image_id] for image_id in ids]


def main() -> None:
    args = parse_args()
    paths = requested_images(args.images, args.image_ids)

    cfg = Config.fromfile(str(args.config))
    # The evaluation pipeline loads ground truth. Direct test inference does not
    # have annotations, so keep only image transforms and input packing.
    pipeline = cfg.test_dataloader.dataset.pipeline
    cfg.test_dataloader.dataset.pipeline = [
        transform for transform in pipeline
        if transform.get("type") != "LoadAnnotations"
    ]
    model = init_detector(cfg, str(args.checkpoint), device="cuda:0")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ("image_id", "label", "conf", "x", "y", "w", "h")
    total_boxes = 0
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for start in range(0, len(paths), args.batch_size):
            batch = paths[start:start + args.batch_size]
            results = inference_detector(model, [str(path) for path in batch])
            if not isinstance(results, list):
                results = [results]
            for path, result in zip(batch, results, strict=True):
                pred = result.pred_instances.cpu()
                boxes = pred.bboxes.numpy()
                scores = pred.scores.numpy()
                labels = pred.labels.numpy()
                for box, score, label in zip(boxes, scores, labels, strict=True):
                    if score < args.score_threshold:
                        continue
                    x1, y1, x2, y2 = map(float, box)
                    if x2 <= x1 or y2 <= y1:
                        continue
                    writer.writerow({
                        "image_id": path.stem,
                        "label": CLASS_NAMES[int(label)],
                        "conf": f"{float(score):.8g}",
                        "x": f"{x1:.8g}",
                        "y": f"{y1:.8g}",
                        "w": f"{x2 - x1:.8g}",
                        "h": f"{y2 - y1:.8g}",
                    })
                    total_boxes += 1
            completed = min(start + args.batch_size, len(paths))
            if start == 0 or completed == len(paths) or completed % 100 == 0:
                print(f"predicted {completed}/{len(paths)} images", flush=True)

    print(f"saved {total_boxes} boxes to {args.output}", flush=True)


if __name__ == "__main__":
    main()
