#!/usr/bin/env python3
"""Run tiled YOLO inference on unlabeled test images for ensembling and submission."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from evaluate_yolo_sliced import merged_predictions, predict_tiles, to_dataframe


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--tile-size", type=int, default=704)
    parser.add_argument("--tile-overlap", type=float, default=0.25)
    parser.add_argument("--score-threshold", type=float, default=0.001)
    parser.add_argument("--max-det", type=int, default=500)
    parser.add_argument("--nms-iou", type=float, default=0.60)
    parser.add_argument("--min-area", type=float, default=200.0)
    parser.add_argument("--sample-submission", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_manifest(images_dir: Path) -> dict[str, dict]:
    paths = sorted(path for path in images_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    result: dict[str, dict] = {}
    for numeric_id, path in enumerate(paths, start=1):
        with Image.open(path) as image:
            width, height = image.size
        result[path.stem] = {
            "id": numeric_id,
            "file_name": path.name,
            "width": width,
            "height": height,
            "original_image_id": path.stem,
        }
    return result


def write_submission(frame: pd.DataFrame, sample_path: Path, output_path: Path) -> None:
    sample = pd.read_csv(sample_path, dtype={"image_id": str})
    if list(sample.columns) != ["image_id", "PredictionString"]:
        raise ValueError(f"Unexpected sample-submission columns: {sample_path}")
    ordered = frame.sort_values(["image_id", "conf"], ascending=[True, False], kind="mergesort")
    strings = {
        image_id: " ".join(
            f"{row.label} {row.conf:.8g} {row.x:.8g} {row.y:.8g} {row.w:.8g} {row.h:.8g}"
            for row in group.itertuples(index=False)
        )
        for image_id, group in ordered.groupby("image_id", sort=False)
    }
    sample["PredictionString"] = sample["image_id"].map(strings).fillna("none")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(output_path, index=False)


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    originals = image_manifest(args.images)
    # predict_tiles reads tiles from --source-images, as in validation.
    args.source_images = args.images

    raw_path = args.output / "raw_tile_predictions.npz"
    if raw_path.exists():
        with np.load(raw_path) as saved:
            raw = {key: saved[key] for key in saved.files}
        print(f"reused {len(raw['scores'])} raw tile predictions", flush=True)
    else:
        raw = predict_tiles(args, raw_path, originals)
        print(f"saved {len(raw['scores'])} raw tile predictions", flush=True)

    frame = to_dataframe(
        merged_predictions(raw, args.nms_iou, args.max_det, args.min_area), originals
    )
    frame.to_csv(args.output / "merged_predictions.csv", index=False)
    write_submission(frame, args.sample_submission, args.submission)
    summary = {
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": sha256(args.checkpoint),
        "images": len(originals),
        "images_with_predictions": int(frame["image_id"].nunique()),
        "raw_tile_predictions": int(len(raw["scores"])),
        "merged_predictions": int(len(frame)),
        "tile_size": args.tile_size,
        "tile_overlap": args.tile_overlap,
        "score_threshold": args.score_threshold,
        "owner_only": True,
        "nms_iou": args.nms_iou,
        "max_det": args.max_det,
        "min_area": args.min_area,
        "submission": str(args.submission),
        "box_format": "xywh in original-image pixels",
        "columns": list(frame.columns),
    }
    (args.output / "prediction_metadata.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
