#!/usr/bin/env python3
"""Classify merged YOLO car/van crops and evaluate embedding-based score fusion."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from convnext_cv_common import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    build_model,
    object_crop,
    sha256,
)
from evaluate_yolo_sliced import to_dataframe, weighted_map
from PIL import Image
from sklearn.model_selection import GroupKFold
from torchvision import transforms
from torchvision.ops import batched_nms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract = subparsers.add_parser("extract")
    extract.add_argument("--raw", type=Path, required=True)
    extract.add_argument("--annotations", type=Path, required=True)
    extract.add_argument("--images", type=Path, required=True)
    extract.add_argument("--classifier", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--nms-iou", type=float, default=0.60)
    extract.add_argument("--batch-size", type=int, default=512)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--features", type=Path, required=True)
    evaluate.add_argument("--annotations-csv", type=Path, required=True)
    evaluate.add_argument("--groups", type=Path, required=True)
    evaluate.add_argument("--weights", type=Path, required=True)
    evaluate.add_argument("--baseline-metrics", type=Path, required=True)
    evaluate.add_argument("--repo", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_raw(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as saved:
        return {key: saved[key] for key in saved.files}


def preliminary_indices(raw: dict[str, np.ndarray], nms_iou: float) -> np.ndarray:
    area = (raw["boxes"][:, 2] - raw["boxes"][:, 0]) * (
        raw["boxes"][:, 3] - raw["boxes"][:, 1]
    )
    valid = raw["owners"].astype(bool) & (area >= 200)
    valid_indices = np.flatnonzero(valid)
    order = np.argsort(raw["image_ids"][valid_indices], kind="stable")
    ordered = valid_indices[order]
    boundaries = np.flatnonzero(np.diff(raw["image_ids"][ordered])) + 1
    selected = []
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
def classify(
    args: argparse.Namespace,
    raw: dict[str, np.ndarray],
    selected: np.ndarray,
    originals: dict[str, dict],
) -> np.ndarray:
    checkpoint = torch.load(args.classifier, map_location="cpu", weights_only=False)
    model = build_model().cuda()
    model.load_state_dict(checkpoint["model"])
    model.eval()
    transform = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)]
    )
    numeric_to_original = {
        int(image["id"]): original_id for original_id, image in originals.items()
    }
    candidate_positions = np.flatnonzero(np.isin(raw["labels"][selected], [0, 1]))
    logits = np.full((len(selected), 2), np.nan, dtype=np.float32)
    pending: list[torch.Tensor] = []
    positions: list[int] = []

    def flush() -> None:
        if not pending:
            return
        batch = torch.stack(pending).cuda(non_blocking=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            values = model(batch).float().cpu().numpy()
        logits[np.asarray(positions)] = values
        pending.clear()
        positions.clear()

    candidate_images = raw["image_ids"][selected[candidate_positions]]
    for image_number, image_id in enumerate(np.unique(candidate_images), start=1):
        current = candidate_positions[candidate_images == image_id]
        original_id = numeric_to_original[int(image_id)]
        original = originals[original_id]
        with Image.open(args.images / str(original["file_name"])) as source:
            source = source.convert("RGB")
            for position in current:
                x1, y1, x2, y2 = raw["boxes"][selected[position]]
                pending.append(
                    transform(object_crop(source, [x1, y1, x2 - x1, y2 - y1]))
                )
                positions.append(int(position))
                if len(pending) >= args.batch_size:
                    flush()
        if image_number % 100 == 0:
            print(
                f"classified {image_number}/{len(np.unique(candidate_images))} images",
                flush=True,
            )
    flush()
    return logits


def extract(args: argparse.Namespace) -> None:
    args.output.mkdir(parents=True, exist_ok=False)
    raw = load_raw(args.raw)
    payload = json.loads(args.annotations.read_text())
    originals = {str(image["original_image_id"]): image for image in payload["images"]}
    selected = preliminary_indices(raw, args.nms_iou)
    logits = classify(args, raw, selected, originals)
    np.save(args.output / "selected.npy", selected)
    np.save(args.output / "classifier_logits.npy", logits)
    (args.output / "images.json").write_text(json.dumps(originals, indent=2) + "\n")
    metadata = {
        "raw_sha256": sha256(args.raw),
        "classifier_sha256": sha256(args.classifier),
        "annotations_sha256": sha256(args.annotations),
        "nms_iou": args.nms_iou,
        "min_area": 200,
        "selected_predictions": len(selected),
        "classified_car_van": int(np.isfinite(logits).all(axis=1).sum()),
        "images": len(originals),
    }
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)


def predictions(
    raw: dict[str, np.ndarray],
    selected: np.ndarray,
    nms_iou: float,
    score_multiplier: np.ndarray | None = None,
    replacement_labels: np.ndarray | None = None,
) -> list[dict]:
    result = []
    order = np.argsort(raw["image_ids"][selected], kind="stable")
    ordered_positions = order
    ordered = selected[order]
    boundaries = np.flatnonzero(np.diff(raw["image_ids"][ordered])) + 1
    for positions in np.split(ordered_positions, boundaries):
        indices = selected[positions]
        labels = raw["labels"][indices].astype(np.int64).copy()
        scores = raw["scores"][indices].copy()
        if score_multiplier is not None:
            scores *= score_multiplier[positions]
        if replacement_labels is not None:
            replace = replacement_labels[positions] >= 0
            labels[replace] = replacement_labels[positions][replace]
        keep = batched_nms(
            torch.from_numpy(raw["boxes"][indices]),
            torch.from_numpy(scores),
            torch.from_numpy(labels),
            nms_iou,
        )[:500].numpy()
        image_id = int(raw["image_ids"][indices[0]])
        for position in keep:
            index = indices[position]
            x1, y1, x2, y2 = raw["boxes"][index].tolist()
            result.append(
                {
                    "image_id": image_id,
                    "category_id": int(labels[position]),
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "score": float(scores[position]),
                }
            )
    return result


def score_predictions(
    frame: pd.DataFrame,
    ground_truth: pd.DataFrame,
    val_ids: list[str],
    weights: dict[str, float],
    competition_evaluate,
) -> dict:
    exact = competition_evaluate(ground_truth, frame, val_ids)
    weighted = weighted_map(
        frame, ground_truth[ground_truth["image_id"].isin(val_ids)], weights
    )
    return {
        "map50": exact["mAP50"],
        "per_class_ap50": exact["AP"],
        "weighted_map50": weighted["map50"],
        "weighted_per_class_ap50": weighted["per_class_ap50"],
    }


def evaluate(args: argparse.Namespace) -> None:
    args.output.mkdir(parents=True, exist_ok=False)
    features = args.features
    metadata = json.loads((features / "metadata.json").read_text())
    raw = load_raw(Path(json.loads((features / "source.json").read_text())["raw"]))
    selected = np.load(features / "selected.npy")
    logits = np.load(features / "classifier_logits.npy")
    originals = json.loads((features / "images.json").read_text())
    nms_iou = float(metadata["nms_iou"])
    labels = raw["labels"][selected].astype(np.int64)
    finite = np.isfinite(logits).all(axis=1)
    shifted = logits[finite] - logits[finite].max(axis=1, keepdims=True)
    probabilities = np.exp(shifted)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    original_probability = np.ones(len(selected), dtype=np.float32)
    original_probability[finite] = probabilities[
        np.arange(len(probabilities)), labels[finite]
    ]

    args.repo = args.repo.resolve()
    import sys

    sys.path.insert(0, str(args.repo))
    from ardahan.evaluate import evaluate as competition_evaluate

    ground_truth = pd.read_csv(args.annotations_csv).drop_duplicates()
    val_ids = list(originals)
    weight_rows = pd.read_csv(args.weights)
    weights = dict(zip(weight_rows["image_id"], weight_rows["weight"], strict=True))

    variants: dict[str, tuple[np.ndarray | None, np.ndarray | None]] = {
        "baseline": (None, None)
    }
    for gamma in (0.10, 0.20, 0.30, 0.40, 0.50, 0.75, 1.0):
        variants[f"rerank_gamma_{gamma:.2f}"] = (original_probability**gamma, None)
    for threshold in (0.80, 0.90, 0.95):
        replacement = np.full(len(selected), -1, dtype=np.int16)
        confidence = probabilities.max(axis=1)
        predicted = probabilities.argmax(axis=1)
        change = confidence >= threshold
        finite_positions = np.flatnonzero(finite)
        replacement[finite_positions[change]] = predicted[change]
        variants[f"hard_relabel_{threshold:.2f}"] = (
            original_probability**0.30,
            replacement,
        )

    frames = {}
    results = {}
    for name, (multiplier, replacement) in variants.items():
        frame = to_dataframe(
            predictions(raw, selected, nms_iou, multiplier, replacement), originals
        )
        frames[name] = frame
        results[name] = score_predictions(
            frame, ground_truth, val_ids, weights, competition_evaluate
        )
        print(
            json.dumps({"variant": name, **results[name]}, sort_keys=True), flush=True
        )

    expected = json.loads(args.baseline_metrics.read_text())["best"]
    reproduced = results["baseline"]
    if abs(reproduced["map50"] - expected["competition"]["map50"]) > 1e-9:
        raise AssertionError("detector-only competition mAP was not reproduced")
    if (
        abs(reproduced["weighted_map50"] - expected["weighted_competition"]["map50"])
        > 1e-9
    ):
        raise AssertionError("detector-only weighted mAP was not reproduced")

    primary_name = "rerank_gamma_0.30"
    primary = results[primary_name]
    baseline = results["baseline"]
    groups_by_image = {}
    with args.groups.open(newline="") as handle:
        for row in csv.DictReader(handle):
            groups_by_image[row["image_id"]] = row["scene_group"]
    fold_reports = []
    val_array = np.asarray(val_ids)
    scene_groups = np.asarray([groups_by_image[image_id] for image_id in val_ids])
    for fold, (_, valid) in enumerate(
        GroupKFold(5).split(val_array, groups=scene_groups), start=1
    ):
        fold_ids = val_array[valid].tolist()
        fold_weights = {image_id: weights[image_id] for image_id in fold_ids}
        baseline_fold = score_predictions(
            frames["baseline"][frames["baseline"]["image_id"].isin(fold_ids)],
            ground_truth,
            fold_ids,
            fold_weights,
            competition_evaluate,
        )
        primary_fold = score_predictions(
            frames[primary_name][frames[primary_name]["image_id"].isin(fold_ids)],
            ground_truth,
            fold_ids,
            fold_weights,
            competition_evaluate,
        )
        fold_reports.append(
            {
                "fold": fold,
                "images": len(fold_ids),
                "map50_gain": primary_fold["map50"] - baseline_fold["map50"],
                "weighted_map50_gain": primary_fold["weighted_map50"]
                - baseline_fold["weighted_map50"],
            }
        )

    gain = primary["map50"] - baseline["map50"]
    weighted_gain = primary["weighted_map50"] - baseline["weighted_map50"]
    accepted = (
        gain >= 0.005
        and weighted_gain >= 0.005
        and primary["per_class_ap50"]["car"] - baseline["per_class_ap50"]["car"]
        >= -0.003
        and primary["per_class_ap50"]["van"] - baseline["per_class_ap50"]["van"]
        >= -0.003
    )
    report = {
        "accepted": bool(accepted),
        "primary_variant": primary_name,
        "primary_precommitted_from_rfdetr": True,
        "map50_gain": gain,
        "weighted_map50_gain": weighted_gain,
        "baseline": baseline,
        "primary": primary,
        "folds": fold_reports,
        "exploratory_variants": results,
    }
    (args.output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    chosen = frames[primary_name] if accepted else frames["baseline"]
    chosen.to_csv(args.output / "selected_predictions.csv", index=False)
    print(json.dumps(report, indent=2), flush=True)

    if os.environ.get("WANDB_MODE"):
        import wandb

        run = wandb.init(
            project=os.environ.get("WANDB_PROJECT", "eli-training"),
            group=os.environ.get("WANDB_RUN_GROUP", "yolo26-convnext-v2"),
            name=os.environ.get("WANDB_NAME", "yolo26-convnext-v2-eval"),
            config={"primary_gamma": 0.30, "nms_iou": nms_iou},
        )
        run.log(
            {
                "baseline/mAP50": baseline["map50"],
                "rerank/mAP50": primary["map50"],
                "rerank/gain": gain,
                "baseline/weighted_mAP50": baseline["weighted_map50"],
                "rerank/weighted_mAP50": primary["weighted_map50"],
                "rerank/weighted_gain": weighted_gain,
            }
        )
        run.finish()


def main() -> None:
    args = parse_args()
    if args.command == "extract":
        extract(args)
        (args.output / "source.json").write_text(
            json.dumps({"raw": str(args.raw)}) + "\n"
        )
    else:
        evaluate(args)


if __name__ == "__main__":
    main()
