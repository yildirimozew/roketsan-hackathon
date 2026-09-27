#!/usr/bin/env python3
"""Run full-grid YOLO inference and score merged original-image predictions."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torchvision.ops import batched_nms


CLASS_NAMES = ("car", "van", "truck", "bus")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--source-images", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--tile-size", type=int, default=704)
    parser.add_argument("--tile-overlap", type=float, default=0.25)
    parser.add_argument("--score-threshold", type=float, default=0.001)
    parser.add_argument("--max-det", type=int, default=500)
    parser.add_argument("--nms-iou", type=float, nargs="+", default=(0.50, 0.55, 0.60, 0.65, 0.70))
    parser.add_argument("--min-area", type=float, default=200.0)
    parser.add_argument("--wandb-run")
    parser.add_argument("--wandb-group", default="yolo26-sliced-pilots")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def tile_origins(length: int, tile_size: int, step: int) -> list[int]:
    if length <= tile_size:
        return [0]
    origins = list(range(0, length - tile_size + 1, step))
    if origins[-1] != length - tile_size:
        origins.append(length - tile_size)
    return origins


def full_grid_tiles(original_images: dict[str, dict], tile_size: int, overlap: float) -> list[dict]:
    step = max(1, round(tile_size * (1 - overlap)))
    result = []
    tile_id = 1
    for original_id, image in original_images.items():
        for top in tile_origins(int(image["height"]), tile_size, step):
            for left in tile_origins(int(image["width"]), tile_size, step):
                result.append(
                    {
                        "id": tile_id,
                        "width": tile_size,
                        "height": tile_size,
                        "original_image_id": original_id,
                        "tile_x": left,
                        "tile_y": top,
                    }
                )
                tile_id += 1
    return result


def ownership_bounds(tile_images: list[dict], original_images: dict[str, dict]) -> dict[int, tuple[float, ...]]:
    origins: dict[str, dict[str, set[int]]] = defaultdict(lambda: {"x": set(), "y": set()})
    for tile in tile_images:
        original_id = str(tile["original_image_id"])
        origins[original_id]["x"].add(int(tile["tile_x"]))
        origins[original_id]["y"].add(int(tile["tile_y"]))
    result = {}
    for tile in tile_images:
        original_id = str(tile["original_image_id"])
        original = original_images[original_id]
        size = int(tile["width"])
        x, y = int(tile["tile_x"]), int(tile["tile_y"])
        xs, ys = sorted(origins[original_id]["x"]), sorted(origins[original_id]["y"])
        xi, yi = xs.index(x), ys.index(y)
        center_x, center_y = x + size / 2, y + size / 2
        left = 0.0 if xi == 0 else ((xs[xi - 1] + size / 2) + center_x) / 2
        right = float(original["width"]) if xi == len(xs) - 1 else (center_x + (xs[xi + 1] + size / 2)) / 2
        top = 0.0 if yi == 0 else ((ys[yi - 1] + size / 2) + center_y) / 2
        bottom = float(original["height"]) if yi == len(ys) - 1 else (center_y + (ys[yi + 1] + size / 2)) / 2
        result[int(tile["id"])] = (left, top, right, bottom)
    return result


def predict_tiles(args: argparse.Namespace, raw_path: Path, original_images: dict[str, dict]) -> dict[str, np.ndarray]:
    from ultralytics import YOLO

    tiles = full_grid_tiles(original_images, args.tile_size, args.tile_overlap)
    bounds = ownership_bounds(tiles, original_images)
    model = YOLO(str(args.checkpoint))
    torch.set_float32_matmul_precision("high")
    collected: dict[str, list[np.ndarray]] = {key: [] for key in ("image_ids", "boxes", "scores", "labels", "owners")}
    for start in range(0, len(tiles), args.batch_size):
        batch = tiles[start:start + args.batch_size]
        images = []
        for tile in batch:
            original_id = str(tile["original_image_id"])
            source_name = original_images[original_id]["file_name"]
            with Image.open(args.source_images / source_name) as source:
                image = source.convert("RGB")
                left, top = int(tile["tile_x"]), int(tile["tile_y"])
                crop = image.crop((left, top, left + args.tile_size, top + args.tile_size))
                if crop.size != (args.tile_size, args.tile_size):
                    padded = Image.new("RGB", (args.tile_size, args.tile_size))
                    padded.paste(crop, (0, 0))
                    crop = padded
                images.append(crop)
        results = model.predict(
            images,
            imgsz=args.tile_size,
            conf=args.score_threshold,
            iou=0.70,
            max_det=args.max_det,
            device=0,
            half=True,
            verbose=False,
        )
        for tile, detection in zip(batch, results, strict=True):
            if detection.boxes is None or len(detection.boxes) == 0:
                continue
            original_id = str(tile["original_image_id"])
            original = original_images[original_id]
            boxes = detection.boxes.xyxy.detach().cpu().numpy().astype(np.float32)
            scores = detection.boxes.conf.detach().cpu().numpy().astype(np.float32)
            labels = detection.boxes.cls.detach().cpu().numpy().astype(np.int16)
            boxes[:, [0, 2]] += float(tile["tile_x"])
            boxes[:, [1, 3]] += float(tile["tile_y"])
            boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, float(original["width"]))
            boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, float(original["height"]))
            valid = (
                (boxes[:, 2] > boxes[:, 0])
                & (boxes[:, 3] > boxes[:, 1])
                & (labels >= 0)
                & (labels < len(CLASS_NAMES))
            )
            centers_x, centers_y = (boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2
            owner_left, owner_top, owner_right, owner_bottom = bounds[int(tile["id"])]
            owners = (
                (centers_x >= owner_left) & (centers_x < owner_right)
                & (centers_y >= owner_top) & (centers_y < owner_bottom)
            )
            collected["image_ids"].append(np.full(valid.sum(), int(original["id"]), dtype=np.int32))
            collected["boxes"].append(boxes[valid])
            collected["scores"].append(scores[valid])
            collected["labels"].append(labels[valid])
            collected["owners"].append(owners[valid])
        completed = min(start + args.batch_size, len(tiles))
        if start == 0 or completed == len(tiles) or completed % (args.batch_size * 10) == 0:
            print(f"predicted {completed}/{len(tiles)} tiles", flush=True)
    raw = {
        "image_ids": np.concatenate(collected["image_ids"]) if collected["image_ids"] else np.empty(0, np.int32),
        "boxes": np.concatenate(collected["boxes"]) if collected["boxes"] else np.empty((0, 4), np.float32),
        "scores": np.concatenate(collected["scores"]) if collected["scores"] else np.empty(0, np.float32),
        "labels": np.concatenate(collected["labels"]) if collected["labels"] else np.empty(0, np.int16),
        "owners": np.concatenate(collected["owners"]) if collected["owners"] else np.empty(0, bool),
    }
    np.savez_compressed(raw_path, **raw)
    return raw


def merged_predictions(raw: dict[str, np.ndarray], nms_iou: float, max_det: int, min_area: float) -> list[dict]:
    predictions = []
    for image_id in np.unique(raw["image_ids"]):
        mask = (raw["image_ids"] == image_id) & raw["owners"]
        boxes = torch.from_numpy(raw["boxes"][mask])
        scores = torch.from_numpy(raw["scores"][mask])
        labels = torch.from_numpy(raw["labels"][mask].astype(np.int64))
        area_mask = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1]) >= min_area
        boxes, scores, labels = boxes[area_mask], scores[area_mask], labels[area_mask]
        keep = batched_nms(boxes, scores, labels, nms_iou)[:max_det]
        for index in keep.tolist():
            x1, y1, x2, y2 = boxes[index].tolist()
            predictions.append({
                "image_id": int(image_id),
                "category_id": int(labels[index]),
                "bbox": [x1, y1, x2 - x1, y2 - y1],
                "score": float(scores[index]),
            })
    return predictions


def to_dataframe(predictions: list[dict], original_images: dict[str, dict]) -> pd.DataFrame:
    numeric_to_original = {int(image["id"]): original_id for original_id, image in original_images.items()}
    rows = []
    for prediction in predictions:
        x, y, width, height = prediction["bbox"]
        rows.append((
            numeric_to_original[int(prediction["image_id"])],
            CLASS_NAMES[int(prediction["category_id"])],
            float(prediction["score"]), x, y, width, height,
        ))
    return pd.DataFrame(rows, columns=["image_id", "label", "conf", "x", "y", "w", "h"])


def weighted_map(preds: pd.DataFrame, gts: pd.DataFrame, weights: dict[str, float]) -> dict:
    def iou_one_to_many(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        x1, y1 = np.maximum(box[0], boxes[:, 0]), np.maximum(box[1], boxes[:, 1])
        x2 = np.minimum(box[0] + box[2], boxes[:, 0] + boxes[:, 2])
        y2 = np.minimum(box[1] + box[3], boxes[:, 1] + boxes[:, 3])
        intersection = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
        return intersection / np.maximum(box[2] * box[3] + boxes[:, 2] * boxes[:, 3] - intersection, 1e-12)

    weight_series = pd.Series(weights, dtype=float)
    aps = {}
    for class_name in CLASS_NAMES:
        ground_truth = gts[gts["label"] == class_name]
        positives = float(weight_series.reindex(ground_truth["image_id"]).sum())
        boxes_by_image = {
            image_id: group[["x", "y", "w", "h"]].to_numpy(float)
            for image_id, group in ground_truth.groupby("image_id")
        }
        used = {image_id: np.zeros(len(boxes), bool) for image_id, boxes in boxes_by_image.items()}
        ranked = preds[preds["label"] == class_name].sort_values("conf", ascending=False, kind="mergesort")
        tp, fp = np.zeros(len(ranked)), np.zeros(len(ranked))
        for index, row in enumerate(ranked.itertuples(index=False)):
            weight = float(weight_series[row.image_id])
            candidates = boxes_by_image.get(row.image_id)
            if candidates is None:
                fp[index] = weight
                continue
            ious = iou_one_to_many(np.array([row.x, row.y, row.w, row.h], float), candidates)
            ious[used[row.image_id]] = -1
            best = int(np.argmax(ious))
            if ious[best] >= 0.5:
                used[row.image_id][best] = True
                tp[index] = weight
            else:
                fp[index] = weight
        recall = np.cumsum(tp) / max(positives, 1e-12)
        precision = np.cumsum(tp) / np.maximum(np.cumsum(tp) + np.cumsum(fp), 1e-12)
        recall = np.concatenate(([0.0], recall, [1.0]))
        precision = np.concatenate(([0.0], precision, [0.0]))
        precision = np.maximum.accumulate(precision[::-1])[::-1]
        changed = np.where(recall[1:] != recall[:-1])[0]
        aps[class_name] = float(np.sum((recall[changed + 1] - recall[changed]) * precision[changed + 1]))
    return {"map50": float(np.mean(list(aps.values()))), "per_class_ap50": aps}


def self_test() -> None:
    gts = pd.DataFrame(
        [("a", "car", 10, 10, 20, 20), ("b", "car", 10, 10, 20, 20)],
        columns=["image_id", "label", "x", "y", "w", "h"],
    )
    predictions = pd.DataFrame(
        [("b", "car", 0.9, 100, 100, 20, 20), ("a", "car", 0.8, 10, 10, 20, 20), ("b", "car", 0.7, 10, 10, 20, 20)],
        columns=["image_id", "label", "conf", "x", "y", "w", "h"],
    )
    result = weighted_map(predictions, gts, {"a": 1.0, "b": 2.0})
    assert 0 < result["per_class_ap50"]["car"] < 1
    assert tile_origins(1400, 704, 528) == [0, 528, 696]
    print("self-test passed")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    args.output.mkdir(parents=True, exist_ok=True)
    annotation_path = args.original / "_annotations.coco.json"
    annotations = json.loads(annotation_path.read_text())
    original_images = {str(image["original_image_id"]): image for image in annotations["images"]}
    raw_path = args.output / "raw_tile_predictions.npz"
    if raw_path.exists():
        with np.load(raw_path) as saved:
            raw = {key: saved[key] for key in saved.files}
    else:
        raw = predict_tiles(args, raw_path, original_images)

    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    from ardahan.evaluate import evaluate as competition_evaluate

    ground_truth = pd.read_csv(repo / "data/train/annotations.csv").drop_duplicates()
    val_ids = list(original_images)
    weight_rows = pd.read_csv(args.weights)
    weights = dict(zip(weight_rows["image_id"], weight_rows["weight"], strict=True))
    all_results = []
    frames: dict[float, pd.DataFrame] = {}
    for nms_iou in args.nms_iou:
        frame = to_dataframe(merged_predictions(raw, nms_iou, args.max_det, args.min_area), original_images)
        frames[nms_iou] = frame
        exact = competition_evaluate(ground_truth, frame, val_ids)
        weighted = weighted_map(frame, ground_truth[ground_truth["image_id"].isin(val_ids)], weights)
        result = {
            "nms_iou": nms_iou,
            "predictions": len(frame),
            "competition": {"map50": exact["mAP50"], "per_class_ap50": exact["AP"]},
            "weighted_competition": weighted,
        }
        all_results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)
    best = max(all_results, key=lambda result: result["weighted_competition"]["map50"])
    best_frame = frames[float(best["nms_iou"])]
    best_frame.to_csv(args.output / "merged_predictions.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    summary = {
        "checkpoint": str(args.checkpoint),
        "evaluation_unit": "scene_holdout_v2 original images after owner-filtered full-grid merging",
        "raw_tile_predictions": int(len(raw["scores"])),
        "best": best,
        "all_results": all_results,
    }
    metrics_path = args.output / "merged_metrics.json"
    metrics_path.write_text(json.dumps(summary, indent=2) + "\n")
    if args.wandb_run:
        import wandb

        run = wandb.init(
            project=os.environ.get("WANDB_PROJECT", "eli-training"),
            name=args.wandb_run,
            group=args.wandb_group,
            job_type="evaluation",
            config={"checkpoint": str(args.checkpoint), "nms_iou": best["nms_iou"], "max_det": args.max_det},
        )
        values = {
            "competition/mAP50": best["competition"]["map50"],
            "weighted_competition/mAP50": best["weighted_competition"]["map50"],
        }
        values.update({f"competition/AP50_{name}": value for name, value in best["competition"]["per_class_ap50"].items()})
        values.update({f"weighted_competition/AP50_{name}": value for name, value in best["weighted_competition"]["per_class_ap50"].items()})
        run.log(values)
        artifact = wandb.Artifact(f"{args.wandb_run}-metrics", type="evaluation")
        artifact.add_file(str(metrics_path))
        run.log_artifact(artifact)
        run.finish()
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
