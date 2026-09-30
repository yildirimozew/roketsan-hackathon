#!/usr/bin/env python3
"""Fuse detections from any set of models and write a submission."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


CLASSES = ("car", "van", "truck", "bus")
COLUMNS = ("image_id", "label", "conf", "x", "y", "w", "h")
DEFAULT_WEIGHTS = {
    "rfdetr": {name: 1.0 for name in CLASSES},
    "cascade": {name: 0.8 for name in CLASSES},
    "yolo": {name: 0.8 for name in CLASSES},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", nargs=2, action="append", default=[], metavar=("NAME", "PATH"),
        help="Named prediction file: RF-DETR .json, image_id,label,conf,x,y,w,h .csv, "
        "or archive.zip::member.csv. Repeat for each model.",
    )
    parser.add_argument("--rfdetr", type=Path)
    parser.add_argument(
        "--rfdetr-map", type=Path,
        help="COCO annotations used to map numeric validation IDs to original IDs",
    )
    parser.add_argument("--cascade", type=Path)
    parser.add_argument("--yolo-zip", type=Path)
    parser.add_argument("--yolo-member")
    parser.add_argument(
        "--weights", default=json.dumps(DEFAULT_WEIGHTS),
        help="JSON {source: weight or {class: weight}}; unlisted sources get 1.0.",
    )
    parser.add_argument("--iou", type=float, default=0.55)
    parser.add_argument("--support-boost", type=float, default=0.05)
    parser.add_argument(
        "--coordinate-mode", choices=("weighted", "best"), default="weighted"
    )
    parser.add_argument("--min-score", type=float, default=0.001)
    parser.add_argument("--max-detections", type=int, default=1000)
    parser.add_argument("--output-predictions", type=Path, required=True)
    parser.add_argument("--sample-submission", type=Path)
    parser.add_argument("--output-submission", type=Path)
    return parser.parse_args()


def read_rfdetr(path: Path, mapping_path: Path | None) -> pd.DataFrame:
    records = json.loads(path.read_text())
    id_map: dict[int, str] = {}
    if mapping_path is not None:
        coco = json.loads(mapping_path.read_text())
        id_map = {
            int(image["id"]): str(
                image.get("original_image_id", Path(image["file_name"]).stem)
            )
            for image in coco["images"]
        }
    rows = []
    for record in records:
        image_id = record["image_id"]
        if isinstance(image_id, int):
            if not id_map:
                raise ValueError("numeric RF-DETR IDs require --rfdetr-map")
            image_id = id_map[image_id]
        category_id = int(record["category_id"])
        label = record.get("class_name", CLASSES[category_id])
        rows.append((str(image_id), label, record["score"], *record["bbox"]))
    return pd.DataFrame(rows, columns=COLUMNS)


def read_yolo(path: Path, member: str) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        with archive.open(member) as handle:
            return pd.read_csv(handle, usecols=COLUMNS)


def read_source(spec: str, mapping_path: Path | None) -> pd.DataFrame:
    if "::" in spec:
        archive, member = spec.split("::", 1)
        return read_yolo(Path(archive), member)
    path = Path(spec)
    if path.suffix == ".json":
        return read_rfdetr(path, mapping_path)
    return pd.read_csv(path, usecols=COLUMNS)


def source_weights(raw: dict, sources: list[str]) -> dict[str, dict[str, float]]:
    unknown = set(raw) - set(sources)
    if unknown and not set(raw) <= set(DEFAULT_WEIGHTS):
        raise ValueError(f"weights name unknown sources: {sorted(unknown)}")
    result = {}
    for source in sources:
        value = raw.get(source, 1.0)
        if isinstance(value, dict):
            if set(value) != set(CLASSES):
                raise ValueError(f"weights for {source} must define {CLASSES}")
            result[source] = {name: float(value[name]) for name in CLASSES}
        else:
            result[source] = {name: float(value) for name in CLASSES}
    return result


def iou_one_to_many(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    left = np.maximum(box[0], boxes[:, 0])
    top = np.maximum(box[1], boxes[:, 1])
    right = np.minimum(box[2], boxes[:, 2])
    bottom = np.minimum(box[3], boxes[:, 3])
    intersection = np.maximum(0.0, right - left) * np.maximum(0.0, bottom - top)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return intersection / np.maximum(area + areas - intersection, 1e-12)


def fuse_group(
    group: pd.DataFrame,
    iou_threshold: float,
    support_boost: float,
    coordinate_mode: str,
) -> list[tuple[float, float, float, float, float]]:
    scores = group["adjusted_score"].to_numpy(np.float64)
    sources = group["source_id"].to_numpy(np.int8)
    # Keep float64 here: float32 can collapse sub-pixel edge boxes to zero
    # width/height when coordinates are near 1,000 pixels.
    xywh = group[["x", "y", "w", "h"]].to_numpy(np.float64)
    boxes = np.column_stack(
        (xywh[:, 0], xywh[:, 1], xywh[:, 0] + xywh[:, 2], xywh[:, 1] + xywh[:, 3])
    )
    order = np.argsort(-scores, kind="stable")

    representatives: list[np.ndarray] = []
    cluster_boxes: list[list[np.ndarray]] = []
    cluster_scores: list[list[float]] = []
    cluster_sources: list[set[int]] = []

    for index in order:
        box = boxes[index]
        source = int(sources[index])
        match = -1
        if representatives:
            eligible = np.asarray([
                source not in used_sources for used_sources in cluster_sources
            ])
            if eligible.any():
                overlaps = iou_one_to_many(box, np.vstack(representatives))
                overlaps[~eligible] = -1
                candidate = int(overlaps.argmax())
                if overlaps[candidate] >= iou_threshold:
                    match = candidate
        if match < 0:
            representatives.append(box.copy())
            cluster_boxes.append([box])
            cluster_scores.append([float(scores[index])])
            cluster_sources.append({source})
            continue

        cluster_boxes[match].append(box)
        cluster_scores[match].append(float(scores[index]))
        cluster_sources[match].add(source)
        if coordinate_mode == "weighted":
            current_boxes = np.vstack(cluster_boxes[match])
            current_scores = np.asarray(cluster_scores[match], dtype=np.float64)
            representatives[match] = np.average(
                current_boxes, axis=0, weights=current_scores
            )

    fused = []
    for box, member_scores, used_sources in zip(
        representatives, cluster_scores, cluster_sources, strict=True
    ):
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        best = max(member_scores)
        support = (len(used_sources) - 1) / 2
        confidence = min(1.0, best + support_boost * support * (1.0 - best))
        fused.append(
            (float(confidence), float(box[0]), float(box[1]),
             float(box[2] - box[0]), float(box[3] - box[1]))
        )
    return fused


def fuse(
    frames: dict[str, pd.DataFrame],
    weights: dict[str, dict[str, float]],
    iou_threshold: float,
    support_boost: float,
    coordinate_mode: str,
    min_score: float,
    max_detections: int,
) -> pd.DataFrame:
    prepared = []
    for source_id, (source, frame) in enumerate(frames.items()):
        current = frame.loc[:, COLUMNS].copy()
        current["source_id"] = source_id
        current["adjusted_score"] = current["conf"] * current["label"].map(
            weights[source]
        )
        current = current[current["adjusted_score"] >= min_score]
        if not current.empty:
            prepared.append(current)
    combined = pd.concat(prepared, ignore_index=True)

    rows = []
    groups = combined.groupby(["image_id", "label"], sort=False)
    total = len(groups)
    for group_number, ((image_id, label), group) in enumerate(groups, start=1):
        for confidence, x, y, width, height in fuse_group(
            group, iou_threshold, support_boost, coordinate_mode
        ):
            rows.append((image_id, label, confidence, x, y, width, height))
        if group_number == 1 or group_number == total or group_number % 1000 == 0:
            print(f"fused {group_number}/{total} image/class groups", flush=True)

    result = pd.DataFrame(rows, columns=COLUMNS)
    result.sort_values(["image_id", "conf"], ascending=[True, False], inplace=True)
    result = result.groupby("image_id", sort=False).head(max_detections)
    return result.reset_index(drop=True)


def write_submission(predictions: pd.DataFrame, sample_path: Path, output: Path) -> None:
    strings = {}
    for image_id, group in predictions.groupby("image_id", sort=False):
        values = []
        for row in group.itertuples(index=False):
            values.extend((
                row.label,
                f"{row.conf:.8g}",
                f"{row.x:.8g}",
                f"{row.y:.8g}",
                f"{row.w:.8g}",
                f"{row.h:.8g}",
            ))
        strings[str(image_id)] = " ".join(values)
    sample = pd.read_csv(sample_path, dtype={"image_id": str})
    sample["PredictionString"] = sample["image_id"].map(strings).fillna("none")
    output.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(output, index=False)


def main() -> None:
    args = parse_args()
    frames = {name: read_source(spec, args.rfdetr_map) for name, spec in args.source}
    if args.rfdetr:
        frames["rfdetr"] = read_rfdetr(args.rfdetr, args.rfdetr_map)
    if args.cascade:
        frames["cascade"] = pd.read_csv(args.cascade, usecols=COLUMNS)
    if args.yolo_zip:
        frames["yolo"] = read_yolo(args.yolo_zip, args.yolo_member)
    if len(frames) < 2:
        raise ValueError("need at least two prediction sources")
    weights = source_weights(json.loads(args.weights), list(frames))
    for source, frame in frames.items():
        print(f"loaded {len(frame)} {source} predictions", flush=True)
    predictions = fuse(
        frames=frames,
        weights=weights,
        iou_threshold=args.iou,
        support_boost=args.support_boost,
        coordinate_mode=args.coordinate_mode,
        min_score=args.min_score,
        max_detections=args.max_detections,
    )
    args.output_predictions.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output_predictions, index=False)
    print(f"saved {len(predictions)} fused predictions", flush=True)
    if args.output_submission:
        if not args.sample_submission:
            raise ValueError("--output-submission requires --sample-submission")
        write_submission(predictions, args.sample_submission, args.output_submission)
        print(f"saved submission to {args.output_submission}", flush=True)


if __name__ == "__main__":
    main()
