#!/usr/bin/env python3
"""Merge RF-DETR tile predictions and evaluate them on original validation images."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from rfdetr import RFDETRLarge
from torchvision.ops import batched_nms, box_iou


CLASS_NAMES = ("car", "van", "truck", "bus")
TTA_MODES = ("none", "flip", "nms", "wbf-mean", "wbf-max")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tiles", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument(
        "--source-images",
        type=Path,
        help="Optional original-image directory; crop tiles on demand instead of reading tile JPEGs.",
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--full-grid", action="store_true")
    parser.add_argument("--tile-size", type=int, default=704)
    parser.add_argument("--tile-overlap", type=float, default=0.25)
    parser.add_argument("--score-threshold", type=float, default=0.001)
    parser.add_argument("--max-det", type=int, default=500)
    parser.add_argument("--nms-iou", type=float, nargs="+", default=(0.4, 0.5, 0.6, 0.7))
    parser.add_argument("--owner-mode", choices=("both", "owner", "all"), default="both")
    parser.add_argument("--min-area", type=float, default=0.0)
    parser.add_argument("--hflip", action="store_true", help="Also predict horizontally mirrored tiles.")
    parser.add_argument("--tta-merge", nargs="+", choices=TTA_MODES, default=("none",))
    parser.add_argument("--tta-iou", type=float, default=0.55)
    parser.add_argument("--wandb-run")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def tile_origins(length: int, tile_size: int, step: int) -> list[int]:
    if length <= tile_size:
        return [0]
    origins = list(range(0, length - tile_size + 1, step))
    if origins[-1] != length - tile_size:
        origins.append(length - tile_size)
    return origins


def full_grid_tiles(
    original_images: dict[str, dict], tile_size: int, overlap: float
) -> list[dict]:
    step = max(1, round(tile_size * (1 - overlap)))
    result = []
    tile_id = 1
    for original_id, image in original_images.items():
        for top in tile_origins(int(image["height"]), tile_size, step):
            for left in tile_origins(int(image["width"]), tile_size, step):
                result.append(
                    {
                        "id": tile_id,
                        "file_name": f"{original_id}__x{left}_y{top}.jpg",
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
        tile_width = int(tile["width"])
        tile_height = int(tile["height"])
        x = int(tile["tile_x"])
        y = int(tile["tile_y"])
        xs = sorted(origins[original_id]["x"])
        ys = sorted(origins[original_id]["y"])
        xi = xs.index(x)
        yi = ys.index(y)
        center_x = x + tile_width / 2
        center_y = y + tile_height / 2
        left = 0.0 if xi == 0 else ((xs[xi - 1] + tile_width / 2) + center_x) / 2
        right = (
            float(original["width"])
            if xi == len(xs) - 1
            else (center_x + (xs[xi + 1] + tile_width / 2)) / 2
        )
        top = 0.0 if yi == 0 else ((ys[yi - 1] + tile_height / 2) + center_y) / 2
        bottom = (
            float(original["height"])
            if yi == len(ys) - 1
            else (center_y + (ys[yi + 1] + tile_height / 2)) / 2
        )
        result[int(tile["id"])] = (left, top, right, bottom)
    return result


def tile_detections(
    model: RFDETRLarge, images: list[Image.Image], threshold: float, hflip: bool
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None]:
    """Predict tiles, optionally also mirrored; boxes are xyxy in unflipped tile pixels."""
    views = [(images, False)]
    if hflip:
        views.append(([ImageOps.mirror(image) for image in images], True))
    per_tile: list[list[tuple[np.ndarray, ...]]] = [[] for _ in images]
    for view_images, flipped in views:
        detections = model.predict(view_images, threshold=threshold, include_source_image=False)
        for index, (image, detection) in enumerate(zip(view_images, detections, strict=True)):
            if len(detection) == 0:
                continue
            boxes = np.asarray(detection.xyxy, dtype=np.float32).copy()
            if flipped:
                boxes[:, [0, 2]] = float(image.width) - boxes[:, [2, 0]]
            per_tile[index].append((
                boxes,
                np.asarray(detection.confidence, dtype=np.float32),
                np.asarray(detection.class_id, dtype=np.int16),
                np.full(len(boxes), flipped, dtype=bool),
            ))
    return [
        tuple(np.concatenate(parts) for parts in zip(*views_for_tile)) if views_for_tile else None
        for views_for_tile in per_tile
    ]


def predict_tiles(args: argparse.Namespace, raw_path: Path) -> dict[str, np.ndarray]:
    tile_annotations = load_json(args.tiles / "_annotations.coco.json")
    original_annotations = load_json(args.original / "_annotations.coco.json")
    original_images = {
        str(image["original_image_id"]): image for image in original_annotations["images"]
    }
    tiles = (
        full_grid_tiles(original_images, args.tile_size, args.tile_overlap)
        if args.full_grid
        else tile_annotations["images"]
    )
    if args.full_grid and args.source_images is None:
        raise ValueError("--full-grid requires --source-images so omitted negative tiles can be cropped on demand")
    bounds = ownership_bounds(tiles, original_images)

    model = RFDETRLarge(
        pretrain_weights=str(args.checkpoint),
        resolution=704,
        num_classes=len(CLASS_NAMES),
    )
    torch.set_float32_matmul_precision("high")

    image_ids: list[np.ndarray] = []
    boxes: list[np.ndarray] = []
    scores: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    owners: list[np.ndarray] = []
    flips: list[np.ndarray] = []
    tiles = sorted(tiles, key=lambda image: int(image["id"]))

    for start in range(0, len(tiles), args.batch_size):
        batch = tiles[start : start + args.batch_size]
        images = []
        for tile in batch:
            if args.source_images is None:
                with Image.open(args.tiles / tile["file_name"]) as image:
                    images.append(image.convert("RGB"))
            else:
                original_id = str(tile["original_image_id"])
                source_name = original_images[original_id]["file_name"]
                with Image.open(args.source_images / source_name) as image:
                    image = image.convert("RGB")
                    left = int(tile["tile_x"])
                    top = int(tile["tile_y"])
                    width = int(tile["width"])
                    height = int(tile["height"])
                    crop = image.crop((left, top, left + width, top + height))
                    if crop.size != (width, height):
                        padded = Image.new("RGB", (width, height))
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
            current_boxes[:, [0, 2]] = current_boxes[:, [0, 2]].clip(0, float(original["width"]))
            current_boxes[:, [1, 3]] = current_boxes[:, [1, 3]].clip(0, float(original["height"]))
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
            current_boxes = current_boxes[valid]
            image_ids.append(np.full(valid.sum(), int(original["id"]), dtype=np.int32))
            boxes.append(current_boxes)
            scores.append(current_scores[valid])
            labels.append(current_labels[valid])
            owners.append(owner[valid])
            flips.append(current_flips[valid])
        print(f"predicted {min(start + args.batch_size, len(tiles))}/{len(tiles)} tiles", flush=True)

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


def fuse_views(
    first: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    second: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    iou_threshold: float,
    score_mode: str,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Weighted-box-fuse two score-sorted views one-to-one within each class."""
    out_boxes, out_scores, out_labels = [], [], []
    missing_factor = 0.5 if score_mode == "mean" else 1.0
    for label in torch.unique(torch.cat((first[2], second[2]))).tolist():
        a = first[2] == label
        b = second[2] == label
        boxes_a, scores_a = first[0][a].double(), first[1][a].double()
        boxes_b, scores_b = second[0][b].double(), second[1][b].double()
        matched_b = torch.zeros(len(boxes_b), dtype=torch.bool)
        overlaps = box_iou(boxes_a, boxes_b).numpy() if len(boxes_a) and len(boxes_b) else None
        for i in range(len(boxes_a)):
            j = -1
            if overlaps is not None:
                row = overlaps[i].copy()
                row[matched_b.numpy()] = -1
                candidate = int(row.argmax())
                if row[candidate] >= iou_threshold:
                    j = candidate
            if j < 0:
                out_boxes.append(boxes_a[i])
                out_scores.append(scores_a[i] * missing_factor)
            else:
                matched_b[j] = True
                weight = scores_a[i] + scores_b[j]
                out_boxes.append((boxes_a[i] * scores_a[i] + boxes_b[j] * scores_b[j]) / weight)
                out_scores.append(
                    weight / 2 if score_mode == "mean" else torch.maximum(scores_a[i], scores_b[j])
                )
            out_labels.append(label)
        for j in torch.nonzero(~matched_b).flatten().tolist():
            out_boxes.append(boxes_b[j])
            out_scores.append(scores_b[j] * missing_factor)
            out_labels.append(label)
    if not out_boxes:
        return torch.empty((0, 4)), torch.empty(0), torch.empty(0, dtype=torch.int64)
    return (
        torch.stack(out_boxes).float(),
        torch.stack(out_scores).float(),
        torch.tensor(out_labels, dtype=torch.int64),
    )


def merged_predictions(
    raw: dict[str, np.ndarray],
    owner_only: bool,
    nms_iou: float,
    max_det: int,
    min_area: float = 0.0,
    tta: str = "none",
    tta_iou: float = 0.55,
) -> list[dict]:
    if tta not in TTA_MODES:
        raise ValueError(f"Unknown TTA merge mode: {tta}")
    flipped = raw.get("flipped")
    if flipped is None:
        if tta != "none":
            raise ValueError(f"TTA merge {tta!r} needs raw predictions made with --hflip")
        flipped = np.zeros(len(raw["scores"]), dtype=bool)
    predictions = []
    for image_id in np.unique(raw["image_ids"]):
        mask = raw["image_ids"] == image_id
        if owner_only:
            mask &= raw["owners"]
        if tta == "none":
            mask &= ~flipped
        elif tta == "flip":
            mask &= flipped
        boxes = torch.from_numpy(raw["boxes"][mask])
        scores = torch.from_numpy(raw["scores"][mask])
        labels = torch.from_numpy(raw["labels"][mask].astype(np.int64))
        view_flipped = torch.from_numpy(flipped[mask])
        if min_area > 0:
            large_enough = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1]) >= min_area
            boxes = boxes[large_enough]
            scores = scores[large_enough]
            labels = labels[large_enough]
            view_flipped = view_flipped[large_enough]
        if tta.startswith("wbf"):
            views = []
            for view in (~view_flipped, view_flipped):
                keep = batched_nms(boxes[view], scores[view], labels[view], nms_iou)
                views.append((boxes[view][keep], scores[view][keep], labels[view][keep]))
            boxes, scores, labels = fuse_views(views[0], views[1], tta_iou, tta.split("-")[1])
            keep = torch.argsort(scores, descending=True, stable=True)
        else:
            keep = batched_nms(boxes, scores, labels, nms_iou)
        keep = keep[:max_det]
        for index in keep.tolist():
            x1, y1, x2, y2 = boxes[index].tolist()
            predictions.append(
                {
                    "image_id": int(image_id),
                    "category_id": int(labels[index]),
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "score": float(scores[index]),
                }
            )
    return predictions


def _iou_one_to_many(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[0] + box[2], boxes[:, 0] + boxes[:, 2])
    y2 = np.minimum(box[1] + box[3], boxes[:, 1] + boxes[:, 3])
    intersection = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    union = box[2] * box[3] + boxes[:, 2] * boxes[:, 3] - intersection
    return intersection / np.maximum(union, 1e-9)


def _average_precision(recall: np.ndarray, precision: np.ndarray) -> float:
    recall = np.concatenate(([0.0], recall, [1.0]))
    precision = np.concatenate(([0.0], precision, [0.0]))
    precision = np.maximum.accumulate(precision[::-1])[::-1]
    changed = np.where(recall[1:] != recall[:-1])[0]
    return float(np.sum((recall[changed + 1] - recall[changed]) * precision[changed + 1]))


def competition_evaluate(annotation_path: Path, predictions: list[dict], min_area: float) -> dict:
    payload = load_json(annotation_path)
    ground_truth: dict[int, dict[int, list[list[float]]]] = defaultdict(lambda: defaultdict(list))
    for annotation in payload["annotations"]:
        if float(annotation["area"]) >= min_area:
            ground_truth[int(annotation["category_id"])][int(annotation["image_id"])].append(
                [float(value) for value in annotation["bbox"]]
            )

    per_class = {}
    n_gt = {}
    for category_id, class_name in enumerate(CLASS_NAMES):
        class_ground_truth = {
            image_id: np.asarray(boxes, dtype=np.float64)
            for image_id, boxes in ground_truth[category_id].items()
        }
        used = {image_id: np.zeros(len(boxes), dtype=bool) for image_id, boxes in class_ground_truth.items()}
        class_predictions = [
            prediction for prediction in predictions if int(prediction["category_id"]) == category_id
        ]
        class_predictions.sort(key=lambda prediction: -float(prediction["score"]))
        positives = sum(len(boxes) for boxes in class_ground_truth.values())
        n_gt[class_name] = positives
        true_positive = np.zeros(len(class_predictions), dtype=np.float64)
        false_positive = np.zeros(len(class_predictions), dtype=np.float64)
        for index, prediction in enumerate(class_predictions):
            image_id = int(prediction["image_id"])
            candidates = class_ground_truth.get(image_id)
            if candidates is None:
                false_positive[index] = 1
                continue
            ious = _iou_one_to_many(np.asarray(prediction["bbox"], dtype=np.float64), candidates)
            ious[used[image_id]] = -1
            best = int(np.argmax(ious))
            if ious[best] >= 0.5:
                used[image_id][best] = True
                true_positive[index] = 1
            else:
                false_positive[index] = 1
        recall = np.cumsum(true_positive) / max(1, positives)
        precision = np.cumsum(true_positive) / np.maximum(
            np.cumsum(true_positive) + np.cumsum(false_positive), 1e-12
        )
        per_class[class_name] = _average_precision(recall, precision)
    return {
        "map50": float(np.mean(list(per_class.values()))),
        "per_class_ap50": per_class,
        "n_gt": n_gt,
        "metric": "competition all-point interpolated AP at IoU 0.5",
        "min_area": min_area,
    }


def evaluate(annotation_path: Path, predictions: list[dict], max_det: int) -> dict:
    ground_truth = COCO(str(annotation_path))
    detections = ground_truth.loadRes(predictions)
    evaluator = COCOeval(ground_truth, detections, "bbox")
    evaluator.params.maxDets = [1, 10, max_det]
    evaluator.evaluate()
    evaluator.accumulate()
    evaluator.summarize()
    precision = evaluator.eval["precision"]
    per_class_ap50 = {}
    per_class_ap50_95 = {}
    for class_index, class_name in enumerate(CLASS_NAMES):
        values50 = precision[0, :, class_index, 0, -1]
        values_all = precision[:, :, class_index, 0, -1]
        per_class_ap50[class_name] = float(values50[values50 > -1].mean())
        per_class_ap50_95[class_name] = float(values_all[values_all > -1].mean())
    return {
        "map50": float(np.mean(list(per_class_ap50.values()))),
        "map50_95": float(np.mean(list(per_class_ap50_95.values()))),
        "per_class_ap50": per_class_ap50,
        "per_class_ap50_95": per_class_ap50_95,
        "predictions": len(predictions),
        "max_det": max_det,
    }


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    raw_path = args.output / "raw_tile_predictions.npz"
    if raw_path.exists():
        with np.load(raw_path) as saved:
            raw = {key: saved[key] for key in saved.files}
        print(f"reused {len(raw['scores'])} raw tile predictions", flush=True)
    else:
        raw = predict_tiles(args, raw_path)
        print(f"saved {len(raw['scores'])} raw tile predictions", flush=True)

    all_results = []
    annotation_path = args.original / "_annotations.coco.json"
    owner_options = {
        "both": (False, True),
        "owner": (True,),
        "all": (False,),
    }[args.owner_mode]
    for owner_only in owner_options:
        for nms_iou in args.nms_iou:
            for tta in args.tta_merge:
                predictions = merged_predictions(
                    raw, owner_only, nms_iou, args.max_det, args.min_area, tta, args.tta_iou
                )
                metrics = evaluate(annotation_path, predictions, args.max_det)
                metrics["competition"] = competition_evaluate(annotation_path, predictions, args.min_area)
                metrics.update({"owner_only": owner_only, "nms_iou": nms_iou, "tta": tta})
                all_results.append(metrics)
                print(json.dumps(metrics, sort_keys=True), flush=True)

    best = max(all_results, key=lambda result: result["competition"]["map50"])
    best_predictions = merged_predictions(
        raw,
        bool(best["owner_only"]),
        float(best["nms_iou"]),
        args.max_det,
        args.min_area,
        str(best["tta"]),
        args.tta_iou,
    )
    (args.output / "merged_predictions.json").write_text(json.dumps(best_predictions))
    summary = {
        "checkpoint": str(args.checkpoint),
        "evaluation_unit": "original validation images after tile merging",
        "raw_tile_predictions": int(len(raw["scores"])),
        "best": best,
        "all_results": all_results,
    }
    (args.output / "merged_metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    if args.wandb_run:
        import wandb

        run = wandb.init(
            project=os.environ.get("WANDB_PROJECT", "eli-training"),
            name=args.wandb_run,
            group=os.environ.get("WANDB_RUN_GROUP", "rfdetr-scene-ab"),
            config={
                "checkpoint": str(args.checkpoint),
                "owner_only": bool(best["owner_only"]),
                "nms_iou": float(best["nms_iou"]),
                "max_det": args.max_det,
                "min_area": args.min_area,
                "evaluation_images": len(load_json(annotation_path)["images"]),
            },
        )
        values = {
            "competition/mAP50": best["competition"]["map50"],
            "coco/mAP50": best["map50"],
            "coco/mAP50_95": best["map50_95"],
        }
        values.update(
            {
                f"competition/AP50_{name}": value
                for name, value in best["competition"]["per_class_ap50"].items()
            }
        )
        run.log(values)
        artifact = wandb.Artifact(f"{args.wandb_run}-metrics", type="evaluation")
        artifact.add_file(str(args.output / "merged_metrics.json"))
        run.log_artifact(artifact)
        run.finish()
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
