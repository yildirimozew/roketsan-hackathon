#!/usr/bin/env python3
"""Run tiled RF-DETR inference on unlabeled test images for ensembling."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from rfdetr import RFDETRLarge

from evaluate_rfdetr_merged import (
    CLASS_NAMES,
    TTA_MODES,
    full_grid_tiles,
    merged_predictions,
    ownership_bounds,
    tile_detections,
)


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--tile-size", type=int, default=704)
    parser.add_argument("--tile-overlap", type=float, default=0.25)
    parser.add_argument("--score-threshold", type=float, default=0.001)
    parser.add_argument("--max-det", type=int, default=1000)
    parser.add_argument("--nms-iou", type=float, default=0.6)
    parser.add_argument("--min-area", type=float, default=0.0)
    parser.add_argument("--hflip", action="store_true", help="Also predict horizontally mirrored tiles.")
    parser.add_argument("--tta-merge", choices=TTA_MODES, default="none")
    parser.add_argument("--tta-iou", type=float, default=0.55)
    parser.add_argument("--sample-submission", type=Path)
    parser.add_argument("--submission", type=Path)
    return parser.parse_args()


def write_submission(predictions: list[dict], sample_path: Path, output_path: Path) -> None:
    grouped: dict[str, list[dict]] = {}
    for prediction in predictions:
        grouped.setdefault(str(prediction["image_id"]), []).append(prediction)

    with sample_path.open(newline="") as source:
        sample = list(csv.DictReader(source))
    if not sample or set(sample[0]) != {"image_id", "PredictionString"}:
        raise ValueError(f"Unexpected sample-submission columns: {sample_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=("image_id", "PredictionString"))
        writer.writeheader()
        for row in sample:
            values: list[str] = []
            for prediction in grouped.get(row["image_id"], []):
                values.extend(
                    [
                        str(prediction["class_name"]),
                        f'{prediction["score"]:.8g}',
                        *(f"{coordinate:.8g}" for coordinate in prediction["bbox"]),
                    ]
                )
            writer.writerow(
                {
                    "image_id": row["image_id"],
                    "PredictionString": " ".join(values) if values else "none",
                }
            )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_manifest(images_dir: Path) -> dict[str, dict]:
    paths = sorted(
        path for path in images_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES
    )
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


def predict_tiles(
    args: argparse.Namespace,
    original_images: dict[str, dict],
    raw_path: Path,
) -> dict[str, np.ndarray]:
    tiles = full_grid_tiles(original_images, args.tile_size, args.tile_overlap)
    tiles.sort(key=lambda image: int(image["id"]))
    bounds = ownership_bounds(tiles, original_images)
    model = RFDETRLarge(
        pretrain_weights=str(args.checkpoint),
        resolution=args.tile_size,
        num_classes=len(CLASS_NAMES),
    )
    torch.set_float32_matmul_precision("high")

    image_ids: list[np.ndarray] = []
    boxes: list[np.ndarray] = []
    scores: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    owners: list[np.ndarray] = []
    flips: list[np.ndarray] = []

    for start in range(0, len(tiles), args.batch_size):
        batch = tiles[start : start + args.batch_size]
        images = []
        for tile in batch:
            original_id = str(tile["original_image_id"])
            original = original_images[original_id]
            with Image.open(args.images / str(original["file_name"])) as source:
                source = source.convert("RGB")
                left = int(tile["tile_x"])
                top = int(tile["tile_y"])
                size = int(tile["width"])
                crop = source.crop((left, top, left + size, top + size))
                if crop.size != (size, size):
                    padded = Image.new("RGB", (size, size))
                    padded.paste(crop, (0, 0))
                    crop = padded
                images.append(crop)

        detections = tile_detections(model, images, args.score_threshold, args.hflip)
        for tile, detection in zip(batch, detections, strict=True):
            if detection is None:
                continue
            original_id = str(tile["original_image_id"])
            original = original_images[original_id]
            current_boxes, current_scores, current_labels, current_flips = detection
            current_boxes[:, [0, 2]] += float(tile["tile_x"])
            current_boxes[:, [1, 3]] += float(tile["tile_y"])
            current_boxes[:, [0, 2]] = current_boxes[:, [0, 2]].clip(
                0, float(original["width"])
            )
            current_boxes[:, [1, 3]] = current_boxes[:, [1, 3]].clip(
                0, float(original["height"])
            )
            valid = (
                (current_boxes[:, 2] > current_boxes[:, 0])
                & (current_boxes[:, 3] > current_boxes[:, 1])
                & (current_labels >= 0)
                & (current_labels < len(CLASS_NAMES))
            )
            centers_x = (current_boxes[:, 0] + current_boxes[:, 2]) / 2
            centers_y = (current_boxes[:, 1] + current_boxes[:, 3]) / 2
            left, top, right, bottom = bounds[int(tile["id"])]
            owner = (
                (centers_x >= left)
                & (centers_x < right)
                & (centers_y >= top)
                & (centers_y < bottom)
            )
            image_ids.append(
                np.full(valid.sum(), int(original["id"]), dtype=np.int32)
            )
            boxes.append(current_boxes[valid])
            scores.append(current_scores[valid])
            labels.append(current_labels[valid])
            owners.append(owner[valid])
            flips.append(current_flips[valid])

        completed = min(start + args.batch_size, len(tiles))
        if start == 0 or completed == len(tiles) or completed % (args.batch_size * 10) == 0:
            print(f"predicted {completed}/{len(tiles)} tiles", flush=True)

    raw = {
        "image_ids": np.concatenate(image_ids),
        "boxes": np.concatenate(boxes),
        "scores": np.concatenate(scores),
        "labels": np.concatenate(labels),
        "owners": np.concatenate(owners),
        "flipped": np.concatenate(flips),
    }
    np.savez_compressed(raw_path, **raw)
    return raw


def main() -> None:
    args = parse_args()
    if (args.sample_submission is None) != (args.submission is None):
        raise ValueError("--sample-submission and --submission must be supplied together")
    args.output.mkdir(parents=True, exist_ok=True)
    originals = image_manifest(args.images)
    numeric_to_name = {
        int(image["id"]): original_id for original_id, image in originals.items()
    }
    mapping = {
        original_id: {
            "numeric_id": int(image["id"]),
            "file_name": str(image["file_name"]),
            "width": int(image["width"]),
            "height": int(image["height"]),
        }
        for original_id, image in originals.items()
    }
    (args.output / "image_id_map.json").write_text(json.dumps(mapping, indent=2) + "\n")

    raw_path = args.output / "raw_tile_predictions.npz"
    if raw_path.exists():
        with np.load(raw_path) as saved:
            raw = {key: saved[key] for key in saved.files}
        print(f"reused {len(raw['scores'])} raw tile predictions", flush=True)
    else:
        raw = predict_tiles(args, originals, raw_path)
        print(f"saved {len(raw['scores'])} raw tile predictions", flush=True)

    numeric_predictions = merged_predictions(
        raw,
        owner_only=True,
        nms_iou=args.nms_iou,
        max_det=args.max_det,
        min_area=args.min_area,
        tta=args.tta_merge,
        tta_iou=args.tta_iou,
    )
    predictions = []
    for prediction in numeric_predictions:
        label = int(prediction["category_id"])
        predictions.append(
            {
                "image_id": numeric_to_name[int(prediction["image_id"])],
                "category_id": label,
                "class_name": CLASS_NAMES[label],
                "bbox": prediction["bbox"],
                "score": prediction["score"],
            }
        )
    (args.output / "merged_predictions.json").write_text(json.dumps(predictions))
    if args.submission is not None:
        write_submission(predictions, args.sample_submission, args.submission)

    np.savez_compressed(
        args.output / "merged_predictions.npz",
        image_ids=np.asarray([p["image_id"] for p in predictions]),
        boxes=np.asarray([p["bbox"] for p in predictions], dtype=np.float32),
        scores=np.asarray([p["score"] for p in predictions], dtype=np.float32),
        labels=np.asarray([p["category_id"] for p in predictions], dtype=np.int16),
    )
    summary = {
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": sha256(args.checkpoint),
        "images": len(originals),
        "raw_tile_predictions": int(len(raw["scores"])),
        "merged_predictions": len(predictions),
        "tile_size": args.tile_size,
        "tile_overlap": args.tile_overlap,
        "score_threshold": args.score_threshold,
        "owner_only": True,
        "nms_iou": args.nms_iou,
        "max_det": args.max_det,
        "min_area": args.min_area,
        "hflip": args.hflip,
        "tta_merge": args.tta_merge,
        "tta_iou": args.tta_iou,
        "submission": str(args.submission) if args.submission else None,
        "box_format": "xywh in original-image pixels",
        "class_names": list(CLASS_NAMES),
    }
    (args.output / "prediction_metadata.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
