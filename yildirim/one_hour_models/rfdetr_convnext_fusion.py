#!/usr/bin/env python3
"""Extract RF-DETR logits, calibrate car/van fusion, and write a submission."""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from convnext_cv_common import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    build_model,
    object_crop,
    sha256,
)
from evaluate_rfdetr_merged import CLASS_NAMES, full_grid_tiles, ownership_bounds
from PIL import Image
from rfdetr import RFDETRLarge
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from torchvision import transforms
from torchvision.ops import batched_nms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract")
    extract.add_argument("--images", type=Path, required=True)
    extract.add_argument("--annotations", type=Path)
    extract.add_argument("--checkpoint", type=Path, required=True)
    extract.add_argument("--classifier", type=Path)
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--batch-size", type=int, default=16)
    extract.add_argument("--classifier-batch-size", type=int, default=512)
    extract.add_argument("--nms-iou", type=float, nargs="+", default=(0.6, 0.7))

    calibrate = subparsers.add_parser("calibrate")
    calibrate.add_argument("--features", type=Path, required=True)
    calibrate.add_argument("--annotations", type=Path, required=True)
    calibrate.add_argument("--groups", type=Path, required=True)
    calibrate.add_argument("--output", type=Path, required=True)

    submit = subparsers.add_parser("submit")
    submit.add_argument("--features", type=Path, required=True)
    submit.add_argument("--calibration", type=Path, required=True)
    submit.add_argument("--sample-submission", type=Path, required=True)
    submit.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text())


def image_manifest(images: Path, annotations: Path | None) -> dict[str, dict]:
    if annotations is not None:
        payload = load_json(annotations)
        return {str(image.get("original_image_id", Path(image["file_name"]).stem)): image for image in payload["images"]}
    result = {}
    for numeric_id, path in enumerate(sorted(images.glob("*.jpg")), start=1):
        with Image.open(path) as image:
            width, height = image.size
        result[path.stem] = {
            "id": numeric_id, "file_name": path.name, "width": width, "height": height,
            "original_image_id": path.stem,
        }
    return result


def sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, -40, 40)
    return 1.0 / (1.0 + np.exp(-values))


def predict_tiles(args: argparse.Namespace, originals: dict[str, dict], raw_path: Path) -> dict[str, np.ndarray]:
    tiles = full_grid_tiles(originals, 704, 0.25)
    tiles.sort(key=lambda item: int(item["id"]))
    bounds = ownership_bounds(tiles, originals)
    model = RFDETRLarge(pretrain_weights=str(args.checkpoint), resolution=704, num_classes=4)
    torch.set_float32_matmul_precision("high")
    saved: dict[str, list[np.ndarray]] = defaultdict(list)

    for start in range(0, len(tiles), args.batch_size):
        batch = tiles[start : start + args.batch_size]
        crops = []
        for tile in batch:
            original_id = str(tile["original_image_id"])
            original = originals[original_id]
            with Image.open(args.images / str(original["file_name"])) as source:
                source = source.convert("RGB")
                left, top, size = int(tile["tile_x"]), int(tile["tile_y"]), int(tile["width"])
                crop = source.crop((left, top, left + size, top + size))
                if crop.size != (size, size):
                    padded = Image.new("RGB", (size, size))
                    padded.paste(crop)
                    crop = padded
                crops.append(crop)
        detections = model.predict(crops, threshold=0.001, include_source_image=False, return_logits=True)
        for tile, detection in zip(batch, detections, strict=True):
            if len(detection) == 0:
                continue
            logits = np.asarray(detection.data["class_logits"], dtype=np.float32)
            query_indices = np.asarray(detection.data["query_index"], dtype=np.int16)
            labels = np.asarray(detection.class_id, dtype=np.int16)
            scores = np.asarray(detection.confidence, dtype=np.float32)
            foreground = (labels >= 0) & (labels < len(CLASS_NAMES))
            expected = sigmoid(logits[np.arange(len(labels))[foreground], labels[foreground]])
            if not np.allclose(expected, scores[foreground], atol=2e-5, rtol=2e-5):
                raise AssertionError("RF-DETR class logits do not align with detection confidence")

            original_id = str(tile["original_image_id"])
            original = originals[original_id]
            boxes = np.asarray(detection.xyxy, dtype=np.float32).copy()
            boxes[:, [0, 2]] += float(tile["tile_x"])
            boxes[:, [1, 3]] += float(tile["tile_y"])
            boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, float(original["width"]))
            boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, float(original["height"]))
            valid = (
                (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
                & (labels >= 0) & (labels < len(CLASS_NAMES))
            )
            centers_x = (boxes[:, 0] + boxes[:, 2]) / 2
            centers_y = (boxes[:, 1] + boxes[:, 3]) / 2
            left, top, right, bottom = bounds[int(tile["id"])]
            owner = (centers_x >= left) & (centers_x < right) & (centers_y >= top) & (centers_y < bottom)
            count = int(valid.sum())
            saved["image_ids"].append(np.full(count, int(original["id"]), dtype=np.int32))
            saved["tile_ids"].append(np.full(count, int(tile["id"]), dtype=np.int32))
            saved["boxes"].append(boxes[valid])
            saved["scores"].append(scores[valid])
            saved["labels"].append(labels[valid])
            saved["owners"].append(owner[valid])
            saved["class_logits"].append(logits[valid])
            saved["query_indices"].append(query_indices[valid])
        completed = min(start + args.batch_size, len(tiles))
        if start == 0 or completed == len(tiles) or completed % (args.batch_size * 20) == 0:
            print(f"predicted {completed}/{len(tiles)} tiles", flush=True)
    raw = {key: np.concatenate(parts) for key, parts in saved.items()}
    np.savez_compressed(raw_path, **raw)
    return raw


def preliminary_indices(raw: dict[str, np.ndarray], nms_iou: float) -> np.ndarray:
    area = (raw["boxes"][:, 2] - raw["boxes"][:, 0]) * (raw["boxes"][:, 3] - raw["boxes"][:, 1])
    valid = raw["owners"].astype(bool) & (area >= 200)
    selected = []
    valid_indices = np.flatnonzero(valid)
    order = np.argsort(raw["image_ids"][valid_indices], kind="stable")
    ordered = valid_indices[order]
    boundaries = np.flatnonzero(np.diff(raw["image_ids"][ordered])) + 1
    for indices in np.split(ordered, boundaries):
        keep = batched_nms(
            torch.from_numpy(raw["boxes"][indices]),
            torch.from_numpy(raw["scores"][indices]),
            torch.from_numpy(raw["labels"][indices].astype(np.int64)),
            nms_iou,
        ).numpy()
        selected.append(indices[keep])
    return np.concatenate(selected).astype(np.int64)


@torch.inference_mode()
def classify_candidates(
    args: argparse.Namespace,
    originals: dict[str, dict],
    raw: dict[str, np.ndarray],
    candidate_indices: np.ndarray,
) -> np.ndarray:
    if args.classifier is None:
        raise ValueError("classifier checkpoint is required to classify candidates")
    checkpoint = torch.load(args.classifier, map_location="cpu", weights_only=False)
    model = build_model().cuda()
    model.load_state_dict(checkpoint["model"])
    model.eval()
    numeric_to_original = {int(image["id"]): original_id for original_id, image in originals.items()}
    logits_output = np.full((len(raw["scores"]), 2), np.nan, dtype=np.float32)
    duplicate_groups: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index in candidate_indices:
        duplicate_groups[(int(raw["tile_ids"][index]), int(raw["query_indices"][index]))].append(int(index))
    representatives = np.asarray([indices[0] for indices in duplicate_groups.values()], dtype=np.int64)
    transform = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)]
    )
    pending_crops: list[torch.Tensor] = []
    pending_indices: list[int] = []

    def flush() -> None:
        if not pending_crops:
            return
        images = torch.stack(pending_crops).cuda(non_blocking=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            values = model(images).float().cpu().numpy()
        logits_output[np.asarray(pending_indices)] = values
        pending_crops.clear()
        pending_indices.clear()

    for image_number, image_id in enumerate(np.unique(raw["image_ids"][representatives]), start=1):
        indices = representatives[raw["image_ids"][representatives] == image_id]
        original_id = numeric_to_original[int(image_id)]
        original = originals[original_id]
        with Image.open(args.images / str(original["file_name"])) as source:
            source = source.convert("RGB")
            for index in indices:
                x1, y1, x2, y2 = raw["boxes"][index]
                crop = object_crop(source, [x1, y1, x2 - x1, y2 - y1])
                pending_crops.append(transform(crop))
                pending_indices.append(int(index))
                if len(pending_crops) >= args.classifier_batch_size:
                    flush()
        if image_number % 100 == 0:
            print(f"classified candidates from {image_number} source images", flush=True)
    flush()
    for indices in duplicate_groups.values():
        logits_output[np.asarray(indices)] = logits_output[indices[0]]
    return logits_output


def extract(args: argparse.Namespace) -> None:
    args.output.mkdir(parents=True, exist_ok=False)
    originals = image_manifest(args.images, args.annotations)
    (args.output / "images.json").write_text(json.dumps(originals, indent=2) + "\n")
    raw = predict_tiles(args, originals, args.output / "raw_predictions.npz")
    all_candidates = []
    for nms_iou in args.nms_iou:
        indices = preliminary_indices(raw, nms_iou)
        np.save(args.output / f"preliminary_nms_{nms_iou:.2f}.npy", indices)
        family_confidence = sigmoid(raw["class_logits"][indices, :2]).max(axis=1)
        candidate = indices[np.isin(raw["labels"][indices], [0, 1]) & (family_confidence >= 0.05)]
        all_candidates.append(candidate)
    candidate_indices = np.unique(np.concatenate(all_candidates))
    classifier_logits = (
        classify_candidates(args, originals, raw, candidate_indices)
        if args.classifier is not None
        else np.full((len(raw["scores"]), 2), np.nan, dtype=np.float32)
    )
    np.save(args.output / "classifier_logits.npy", classifier_logits)
    metadata = {
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": sha256(args.checkpoint),
        "classifier": str(args.classifier) if args.classifier else None,
        "classifier_sha256": sha256(args.classifier) if args.classifier else None,
        "images": len(originals),
        "raw_predictions": len(raw["scores"]),
        "classified_candidates": len(candidate_indices) if args.classifier else 0,
        "tile_size": 704, "tile_overlap": 0.25, "min_area": 200,
        "candidate_threshold": 0.05, "nms_candidates": list(args.nms_iou),
    }
    (args.output / "extraction_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)


def xywh_iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    left = np.maximum(box[0], boxes[:, 0])
    top = np.maximum(box[1], boxes[:, 1])
    right = np.minimum(box[0] + box[2], boxes[:, 0] + boxes[:, 2])
    bottom = np.minimum(box[1] + box[3], boxes[:, 1] + boxes[:, 3])
    intersection = np.maximum(0, right - left) * np.maximum(0, bottom - top)
    union = box[2] * box[3] + boxes[:, 2] * boxes[:, 3] - intersection
    return intersection / np.maximum(union, 1e-12)


def average_precision(recall: np.ndarray, precision: np.ndarray) -> float:
    recall = np.concatenate(([0.0], recall, [1.0]))
    precision = np.concatenate(([0.0], precision, [0.0]))
    precision = np.maximum.accumulate(precision[::-1])[::-1]
    changed = np.where(recall[1:] != recall[:-1])[0]
    return float(np.sum((recall[changed + 1] - recall[changed]) * precision[changed + 1]))


def competition_metric(
    payload: dict,
    predictions: list[dict],
    allowed_images: set[int] | None = None,
    category_ids: tuple[int, ...] = tuple(range(len(CLASS_NAMES))),
) -> dict:
    ground: dict[int, dict[int, list[list[float]]]] = defaultdict(lambda: defaultdict(list))
    for annotation in payload["annotations"]:
        image_id = int(annotation["image_id"])
        if float(annotation["area"]) >= 200 and (allowed_images is None or image_id in allowed_images):
            ground[int(annotation["category_id"])][image_id].append(annotation["bbox"])
    values = {}
    for category in category_ids:
        name = CLASS_NAMES[category]
        category_ground = {image_id: np.asarray(boxes, dtype=np.float64) for image_id, boxes in ground[category].items()}
        used = {image_id: np.zeros(len(boxes), dtype=bool) for image_id, boxes in category_ground.items()}
        selected = [p for p in predictions if int(p["category_id"]) == category and (allowed_images is None or int(p["image_id"]) in allowed_images)]
        selected.sort(key=lambda item: -float(item["score"]))
        positives = sum(len(boxes) for boxes in category_ground.values())
        true_positive = np.zeros(len(selected))
        false_positive = np.zeros(len(selected))
        for position, prediction in enumerate(selected):
            image_id = int(prediction["image_id"])
            candidates = category_ground.get(image_id)
            if candidates is None:
                false_positive[position] = 1
                continue
            overlaps = xywh_iou(np.asarray(prediction["bbox"], dtype=float), candidates)
            overlaps[used[image_id]] = -1
            best = int(np.argmax(overlaps))
            if overlaps[best] >= 0.5:
                used[image_id][best] = True
                true_positive[position] = 1
            else:
                false_positive[position] = 1
        recall = np.cumsum(true_positive) / max(1, positives)
        precision = np.cumsum(true_positive) / np.maximum(np.cumsum(true_positive) + np.cumsum(false_positive), 1e-12)
        values[name] = average_precision(recall, precision)
    return {"map50": float(np.mean(list(values.values()))), "per_class_ap50": values}


def final_predictions(
    raw: dict[str, np.ndarray],
    selected: np.ndarray,
    nms_iou: float,
    decisions: dict[int, float] | None = None,
    bias: float = 0.0,
    allowed_images: set[int] | None = None,
) -> list[dict]:
    predictions = []
    order = np.argsort(raw["image_ids"][selected], kind="stable")
    ordered = selected[order]
    boundaries = np.flatnonzero(np.diff(raw["image_ids"][ordered])) + 1
    for indices in np.split(ordered, boundaries):
        image_id = int(raw["image_ids"][indices[0]])
        if allowed_images is not None and int(image_id) not in allowed_images:
            continue
        labels = raw["labels"][indices].astype(np.int64).copy()
        scores = raw["scores"][indices].copy()
        if decisions:
            for position, index in enumerate(indices):
                value = decisions.get(int(index))
                if value is not None:
                    labels[position] = 1 if value + bias >= 0 else 0
                    scores[position] = sigmoid(raw["class_logits"][index, :2]).max()
        keep = batched_nms(
            torch.from_numpy(raw["boxes"][indices]), torch.from_numpy(scores),
            torch.from_numpy(labels), nms_iou,
        )[:500].numpy()
        for position in keep:
            index = indices[position]
            x1, y1, x2, y2 = raw["boxes"][index].tolist()
            predictions.append({
                "image_id": int(image_id), "category_id": int(labels[position]),
                "bbox": [x1, y1, x2 - x1, y2 - y1], "score": float(scores[position]),
            })
    return predictions


def matched_features(
    raw: dict[str, np.ndarray], selected: np.ndarray, classifier_logits: np.ndarray,
    payload: dict, numeric_to_original: dict[int, str], image_to_group: dict[str, str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cv_ground: dict[int, list[tuple[int, list[float]]]] = defaultdict(list)
    for annotation in payload["annotations"]:
        if int(annotation["category_id"]) in (0, 1) and float(annotation["area"]) >= 200:
            cv_ground[int(annotation["image_id"])].append((int(annotation["category_id"]), annotation["bbox"]))
    features, targets, groups = [], [], []
    finite = np.isfinite(classifier_logits[selected]).all(axis=1)
    candidates = selected[finite]
    family_scores = sigmoid(raw["class_logits"][candidates, :2]).max(axis=1)
    for image_id in np.unique(raw["image_ids"][candidates]):
        truth = cv_ground.get(int(image_id), [])
        if not truth:
            continue
        truth_labels = np.asarray([item[0] for item in truth], dtype=np.int64)
        truth_boxes = np.asarray([item[1] for item in truth], dtype=np.float64)
        image_mask = raw["image_ids"][candidates] == image_id
        image_candidates = candidates[image_mask]
        image_scores = family_scores[image_mask]
        used = np.zeros(len(truth), dtype=bool)
        for index in image_candidates[np.argsort(-image_scores, kind="stable")]:
            x1, y1, x2, y2 = raw["boxes"][index]
            overlaps = xywh_iou(np.asarray([x1, y1, x2 - x1, y2 - y1]), truth_boxes)
            overlaps[used] = -1
            best = int(np.argmax(overlaps))
            if overlaps[best] < 0.5:
                continue
            used[best] = True
            features.append([
                float(raw["class_logits"][index, 1] - raw["class_logits"][index, 0]),
                float(classifier_logits[index, 1] - classifier_logits[index, 0]),
            ])
            targets.append(int(truth_labels[best]))
            original_id = numeric_to_original[int(image_id)]
            groups.append(image_to_group[original_id])
    return np.asarray(features), np.asarray(targets), np.asarray(groups)


def fit_calibrator(features: np.ndarray, targets: np.ndarray) -> tuple[StandardScaler, LogisticRegression]:
    scaler = StandardScaler().fit(features)
    model = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(scaler.transform(features), targets)
    return scaler, model


def decision_values(
    raw: dict[str, np.ndarray], selected: np.ndarray, classifier_logits: np.ndarray,
    scaler: StandardScaler, model: LogisticRegression,
) -> dict[int, float]:
    finite = np.isfinite(classifier_logits[selected]).all(axis=1)
    indices = selected[finite]
    features = np.column_stack((
        raw["class_logits"][indices, 1] - raw["class_logits"][indices, 0],
        classifier_logits[indices, 1] - classifier_logits[indices, 0],
    ))
    values = model.decision_function(scaler.transform(features))
    return dict(zip(map(int, indices), map(float, values), strict=True))


_BIAS_CONTEXT: tuple | None = None


def score_bias(bias: float) -> tuple[float, float]:
    if _BIAS_CONTEXT is None:
        raise RuntimeError("bias worker was not initialized")
    raw, selected, nms_iou, decisions, payload, allowed_images = _BIAS_CONTEXT
    predictions = final_predictions(raw, selected, nms_iou, decisions, bias, allowed_images)
    metric = competition_metric(payload, predictions, allowed_images, category_ids=(0, 1))
    score = (metric["per_class_ap50"]["car"] + metric["per_class_ap50"]["van"]) / 2
    return bias, float(score)


def initialize_bias_worker() -> None:
    torch.set_num_threads(1)


def tune_bias(
    raw: dict[str, np.ndarray], selected: np.ndarray, nms_iou: float,
    decisions: dict[int, float], payload: dict, allowed_images: set[int],
) -> tuple[float, float]:
    global _BIAS_CONTEXT
    biases = [float(value) for value in np.round(np.arange(-1.5, 1.5001, 0.05), 2)]
    _BIAS_CONTEXT = (raw, selected, nms_iou, decisions, payload, allowed_images)
    workers = min(int(os.environ.get("SLURM_CPUS_PER_TASK", "1")), len(biases))
    if workers == 1:
        results = list(map(score_bias, biases))
    else:
        context = mp.get_context("fork")
        with context.Pool(workers, initializer=initialize_bias_worker) as pool:
            results = pool.map(score_bias, biases, chunksize=1)
    _BIAS_CONTEXT = None
    return max(results, key=lambda item: item[1])


def calibrate(args: argparse.Namespace) -> None:
    args.output.mkdir(parents=True, exist_ok=False)
    with np.load(args.features / "raw_predictions.npz") as saved:
        raw = {key: saved[key] for key in saved.files}
    classifier_logits = np.load(args.features / "classifier_logits.npy")
    originals = load_json(args.features / "images.json")
    numeric_to_original = {int(image["id"]): original_id for original_id, image in originals.items()}
    payload = load_json(args.annotations)
    image_to_group = {}
    with args.groups.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["split"] == "val":
                image_to_group[row["image_id"]] = row["scene_group"]

    baselines = {}
    selections = {}
    for nms_iou in (0.6, 0.7):
        selected = np.load(args.features / f"preliminary_nms_{nms_iou:.2f}.npy")
        selections[nms_iou] = selected
        predictions = final_predictions(raw, selected, nms_iou)
        baselines[nms_iou] = competition_metric(payload, predictions)
    nms_iou = max(baselines, key=lambda value: baselines[value]["map50"])
    selected = selections[nms_iou]
    features, targets, groups = matched_features(
        raw, selected, classifier_logits, payload, numeric_to_original, image_to_group
    )
    if len(features) < 1000 or len(np.unique(targets)) != 2:
        raise ValueError(f"insufficient matched calibration examples: {len(features)}")

    oof_decisions: dict[int, float] = {}
    fold_reports = []
    splitter = GroupKFold(5)
    for fold, (train_positions, valid_positions) in enumerate(splitter.split(features, targets, groups), start=1):
        scaler, model = fit_calibrator(features[train_positions], targets[train_positions])
        train_groups = set(groups[train_positions])
        valid_groups = set(groups[valid_positions])
        train_images = {
            numeric_id for numeric_id, original_id in numeric_to_original.items()
            if image_to_group[original_id] in train_groups
        }
        valid_images = {
            numeric_id for numeric_id, original_id in numeric_to_original.items()
            if image_to_group[original_id] in valid_groups
        }
        all_values = decision_values(raw, selected, classifier_logits, scaler, model)
        bias, train_cv_ap = tune_bias(raw, selected, nms_iou, all_values, payload, train_images)
        for index, value in all_values.items():
            if int(raw["image_ids"][index]) in valid_images:
                oof_decisions[index] = value + bias
        fold_reports.append({
            "fold": fold, "bias": bias, "training_car_van_map50": train_cv_ap,
            "train_examples": len(train_positions), "valid_examples": len(valid_positions),
            "coefficients": model.coef_[0].tolist(), "intercept": float(model.intercept_[0]),
            "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
        })
        print(json.dumps(fold_reports[-1], sort_keys=True), flush=True)

    oof_predictions = final_predictions(raw, selected, nms_iou, oof_decisions)
    oof_metrics = competition_metric(payload, oof_predictions)
    baseline = baselines[nms_iou]
    scaler, model = fit_calibrator(features, targets)
    final_values = decision_values(raw, selected, classifier_logits, scaler, model)
    final_bias, fitted_cv_ap = tune_bias(
        raw, selected, nms_iou, final_values, payload, set(numeric_to_original)
    )
    fitted_predictions = final_predictions(raw, selected, nms_iou, final_values, final_bias)
    fitted_metrics = competition_metric(payload, fitted_predictions)

    overall_gain = oof_metrics["map50"] - baseline["map50"]
    baseline_cv = (baseline["per_class_ap50"]["car"] + baseline["per_class_ap50"]["van"]) / 2
    oof_cv = (oof_metrics["per_class_ap50"]["car"] + oof_metrics["per_class_ap50"]["van"]) / 2
    accepted = (
        overall_gain >= 0.005
        and oof_cv - baseline_cv >= 0.010
        and oof_metrics["per_class_ap50"]["car"] - baseline["per_class_ap50"]["car"] >= -0.003
        and oof_metrics["per_class_ap50"]["van"] - baseline["per_class_ap50"]["van"] >= -0.003
    )
    calibration = {
        "name": "rfdetr-convnext-car-van-logit-fusion",
        "accepted": bool(accepted), "nms_iou": nms_iou, "candidate_threshold": 0.05,
        "feature_names": ["rfdetr_van_minus_car", "convnext_van_minus_car"],
        "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
        "coefficients": model.coef_[0].tolist(), "intercept": float(model.intercept_[0]),
        "bias": final_bias, "matched_examples": len(features),
        "features_sha256": sha256(args.features / "raw_predictions.npz"),
    }
    report = {
        "accepted": bool(accepted), "selected_nms_iou": nms_iou,
        "baselines": {str(key): value for key, value in baselines.items()},
        "oof": oof_metrics, "fitted_full_validation": fitted_metrics,
        "overall_oof_gain": overall_gain, "car_van_oof_gain": oof_cv - baseline_cv,
        "folds": fold_reports, "final_training_car_van_map50": fitted_cv_ap,
    }
    (args.output / "calibration.json").write_text(json.dumps(calibration, indent=2) + "\n")
    (args.output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "selected.json").write_text(json.dumps({"accepted": bool(accepted)}, indent=2) + "\n")
    (args.output / "baseline_predictions.json").write_text(json.dumps(final_predictions(raw, selected, nms_iou)))
    (args.output / "oof_fused_predictions.json").write_text(json.dumps(oof_predictions))
    print(json.dumps(report, indent=2), flush=True)

    if os.environ.get("WANDB_MODE"):
        import wandb
        run = wandb.init(
            project=os.environ.get("WANDB_PROJECT", "eli-training"),
            group=os.environ.get("WANDB_RUN_GROUP", "rfdetr-convnext-cv"),
            name=os.environ.get("WANDB_NAME", "rfdetr-convnext-cv-calibration"),
            config=calibration,
        )
        run.log({
            "baseline/mAP50": baseline["map50"], "oof/mAP50": oof_metrics["map50"],
            "oof/gain": overall_gain,
            **{f"baseline/AP50_{name}": value for name, value in baseline["per_class_ap50"].items()},
            **{f"oof/AP50_{name}": value for name, value in oof_metrics["per_class_ap50"].items()},
        })
        run.finish()


def write_submission(predictions: list[dict], originals: dict[str, dict], sample: Path, output: Path) -> None:
    numeric_to_original = {int(image["id"]): original_id for original_id, image in originals.items()}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for prediction in predictions:
        grouped[numeric_to_original[int(prediction["image_id"])]].append(prediction)
    with sample.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("image_id", "PredictionString"))
        writer.writeheader()
        for row in rows:
            values = []
            for prediction in grouped.get(row["image_id"], []):
                values.extend([
                    CLASS_NAMES[int(prediction["category_id"])], f'{prediction["score"]:.8g}',
                    *(f"{coordinate:.8g}" for coordinate in prediction["bbox"]),
                ])
            writer.writerow({"image_id": row["image_id"], "PredictionString": " ".join(values) if values else "none"})


def submit(args: argparse.Namespace) -> None:
    args.output.mkdir(parents=True, exist_ok=False)
    calibration = load_json(args.calibration)
    with np.load(args.features / "raw_predictions.npz") as saved:
        raw = {key: saved[key] for key in saved.files}
    classifier_logits = np.load(args.features / "classifier_logits.npy")
    originals = load_json(args.features / "images.json")
    nms_iou = float(calibration["nms_iou"])
    selected = np.load(args.features / f"preliminary_nms_{nms_iou:.2f}.npy")
    decisions = None
    bias = 0.0
    if calibration["accepted"]:
        scaler = StandardScaler()
        scaler.mean_ = np.asarray(calibration["scaler_mean"])
        scaler.scale_ = np.asarray(calibration["scaler_scale"])
        scaler.var_ = scaler.scale_ ** 2
        scaler.n_features_in_ = len(scaler.mean_)
        model = LogisticRegression()
        model.classes_ = np.asarray([0, 1])
        model.coef_ = np.asarray([calibration["coefficients"]])
        model.intercept_ = np.asarray([calibration["intercept"]])
        model.n_features_in_ = len(calibration["coefficients"])
        decisions = decision_values(raw, selected, classifier_logits, scaler, model)
        bias = float(calibration["bias"])
    predictions = final_predictions(raw, selected, nms_iou, decisions, bias)
    (args.output / "merged_predictions.json").write_text(json.dumps(predictions))
    write_submission(predictions, originals, args.sample_submission, args.output / "submission.csv")
    metadata = {
        "fusion_applied": bool(calibration["accepted"]), "predictions": len(predictions),
        "nms_iou": nms_iou, "max_det": 500, "min_area": 200,
        "calibration_sha256": sha256(args.calibration),
    }
    (args.output / "prediction_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)


def main() -> None:
    args = parse_args()
    if args.command == "extract":
        extract(args)
    elif args.command == "calibrate":
        calibrate(args)
    else:
        submit(args)


if __name__ == "__main__":
    main()
