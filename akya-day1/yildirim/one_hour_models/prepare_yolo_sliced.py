#!/usr/bin/env python3
"""Prepare deterministic sliced YOLO datasets for the three scene-holdout pilots."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

from prepare_rfdetr_ab import (
    CLASS_NAMES,
    centered_records,
    grid_records,
    image_sizes,
    read_ids,
    select_training_grid,
    sha256_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--split-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tile-size", type=int, default=704)
    parser.add_argument("--tile-overlap", type=float, default=0.25)
    parser.add_argument("--min-visible", type=float, default=0.60)
    parser.add_argument("--negative-ratio", type=float, default=0.20)
    parser.add_argument("--centered-ratios", type=float, nargs="+", default=(0.25, 0.40))
    parser.add_argument("--center-jitter", type=float, default=0.15)
    parser.add_argument("--anchor-min-visible", type=float, default=0.80)
    parser.add_argument("--max-centered-per-image", type=int, default=4)
    parser.add_argument("--high-ratio-max-centered-per-image", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def read_annotations_deduplicated(path: Path) -> tuple[dict[str, list[dict[str, object]]], int]:
    result: dict[str, list[dict[str, object]]] = defaultdict(list)
    seen: set[tuple[str, str, str, str, str, str]] = set()
    duplicates = 0
    with path.open(newline="") as handle:
        for source_row, row in enumerate(csv.DictReader(handle), start=1):
            key = tuple(row[name] for name in ("image_id", "x", "y", "w", "h", "label"))
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            result[row["image_id"]].append(
                {
                    "annotation_id": source_row,
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "w": float(row["w"]),
                    "h": float(row["h"]),
                    "label": row["label"],
                }
            )
    return result, duplicates


def record_name(record: dict[str, object]) -> str:
    if record["kind"] == "centered":
        suffix = f"focus-{record['focus_class']}-a{record['focus_annotation_id']}"
    else:
        suffix = "grid"
    return f"{record['image_id']}__{suffix}_x{record['left']}_y{record['top']}"


def write_yolo_records(
    root: Path, records: list[dict[str, object]], tile_size: int
) -> tuple[list[Path], dict[str, object]]:
    images_dir = root / "images" / "train"
    labels_dir = root / "labels" / "train"
    images_dir.mkdir(parents=True, exist_ok=False)
    labels_dir.mkdir(parents=True, exist_ok=False)
    records.sort(
        key=lambda record: (
            str(record["image_id"]),
            str(record["kind"]),
            int(record["top"]),
            int(record["left"]),
            int(record["focus_annotation_id"] or 0),
        )
    )
    paths: list[Path] = []
    class_counts: Counter[str] = Counter()
    opened_source: Path | None = None
    opened_image: Image.Image | None = None
    try:
        for record in records:
            source = Path(record["source"])
            if source != opened_source:
                if opened_image is not None:
                    opened_image.close()
                opened_image = Image.open(source).convert("RGB")
                opened_source = source
            stem = record_name(record)
            image_path = images_dir / f"{stem}.jpg"
            label_path = labels_dir / f"{stem}.txt"
            left, top = int(record["left"]), int(record["top"])
            assert opened_image is not None
            crop = opened_image.crop((left, top, left + tile_size, top + tile_size))
            if crop.size != (tile_size, tile_size):
                padded = Image.new("RGB", (tile_size, tile_size))
                padded.paste(crop, (0, 0))
                crop = padded
            crop.save(image_path, quality=92, optimize=False)
            lines = []
            for box, clipped in record["boxes"]:
                x, y, width, height = map(float, clipped)
                label = str(box["label"])
                class_counts[label] += 1
                class_id = CLASS_NAMES.index(label)
                lines.append(
                    f"{class_id} {(x + width / 2) / tile_size:.8f} "
                    f"{(y + height / 2) / tile_size:.8f} {width / tile_size:.8f} "
                    f"{height / tile_size:.8f}"
                )
            label_path.write_text("\n".join(lines) + ("\n" if lines else ""))
            paths.append(image_path)
    finally:
        if opened_image is not None:
            opened_image.close()
    return paths, {
        "images": len(records),
        "positive_images": sum(bool(record["boxes"]) for record in records),
        "negative_images": sum(not record["boxes"] for record in records),
        "annotations": sum(class_counts.values()),
        "annotation_class_counts": {name: class_counts[name] for name in CLASS_NAMES},
    }


def write_original_validation(
    output: Path,
    ids: list[str],
    paths: dict[str, Path],
    sizes: dict[str, tuple[int, int]],
    annotations: dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    image_dir = output / "validation" / "images" / "val"
    label_dir = output / "validation" / "labels" / "val"
    image_dir.mkdir(parents=True, exist_ok=False)
    label_dir.mkdir(parents=True, exist_ok=False)
    images = []
    coco_annotations = []
    annotation_id = 1
    for numeric_id, image_id in enumerate(ids, start=1):
        source = paths[image_id]
        (image_dir / source.name).symlink_to(source)
        width, height = sizes[image_id]
        images.append(
            {
                "id": numeric_id,
                "file_name": source.name,
                "width": width,
                "height": height,
                "original_image_id": image_id,
            }
        )
        label_lines = []
        for box in annotations.get(image_id, []):
            x, y, box_width, box_height = (
                float(box["x"]),
                float(box["y"]),
                float(box["w"]),
                float(box["h"]),
            )
            class_id = CLASS_NAMES.index(str(box["label"]))
            x1, y1 = min(max(x, 0.0), width), min(max(y, 0.0), height)
            x2 = min(max(x + box_width, 0.0), width)
            y2 = min(max(y + box_height, 0.0), height)
            if x2 > x1 and y2 > y1:
                label_lines.append(
                    f"{class_id} {((x1 + x2) / 2) / width:.8f} {((y1 + y2) / 2) / height:.8f} "
                    f"{(x2 - x1) / width:.8f} {(y2 - y1) / height:.8f}"
                )
            coco_annotations.append(
                {
                    "id": annotation_id,
                    "image_id": numeric_id,
                    "category_id": class_id,
                    "bbox": [x, y, box_width, box_height],
                    "area": box_width * box_height,
                    "iscrowd": 0,
                }
            )
            annotation_id += 1
        (label_dir / f"{image_id}.txt").write_text(
            "\n".join(label_lines) + ("\n" if label_lines else "")
        )
    payload = {
        "info": {"description": "Roketsan scene_holdout_v2 original validation"},
        "licenses": [],
        "images": images,
        "annotations": coco_annotations,
        "categories": [
            {"id": index, "name": name, "supercategory": "vehicle"}
            for index, name in enumerate(CLASS_NAMES)
        ],
    }
    annotation_path = image_dir / "_annotations.coco.json"
    annotation_path.write_text(json.dumps(payload))
    return {
        "images": len(images),
        "annotations": len(coco_annotations),
        "annotations_sha256": sha256_file(annotation_path),
    }


def ratio_name(ratio: float) -> str:
    return f"ratio{round(ratio * 100):02d}"


def write_manifest(output: Path, name: str, paths: list[Path]) -> Path:
    path = output / name
    # Ultralytics anchors only entries beginning with "./" to the manifest's
    # directory. Bare relative paths instead resolve against the launch CWD.
    path.write_text("".join(f"./{os.path.relpath(item, output)}\n" for item in paths))
    return path


def main() -> None:
    args = parse_args()
    repo = args.repo.resolve()
    split_dir = args.split_dir.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)

    annotation_path = repo / "data" / "train" / "annotations.csv"
    images_dir = repo / "data" / "train" / "images"
    manifests = {"train": split_dir / "train.txt", "valid": split_dir / "val.txt"}
    split_ids = {name: read_ids(path) for name, path in manifests.items()}
    if set(split_ids["train"]) & set(split_ids["valid"]):
        raise ValueError("Train and validation manifests overlap")
    if len(split_ids["train"]) != 5176 or len(split_ids["valid"]) != 1295:
        raise ValueError("Unexpected scene_holdout_v2 split sizes")

    annotations, duplicate_rows = read_annotations_deduplicated(annotation_path)
    all_ids = split_ids["train"] + split_ids["valid"]
    paths, sizes = image_sizes(images_dir, all_ids)
    train_paths = {image_id: paths[image_id] for image_id in split_ids["train"]}
    train_sizes = {image_id: sizes[image_id] for image_id in split_ids["train"]}
    valid_paths = {image_id: paths[image_id] for image_id in split_ids["valid"]}
    valid_sizes = {image_id: sizes[image_id] for image_id in split_ids["valid"]}

    validation_stats = write_original_validation(
        output, split_ids["valid"], valid_paths, valid_sizes, annotations
    )
    validation_paths = [output / "validation" / "images" / "val" / paths[i].name for i in split_ids["valid"]]
    validation_manifest = write_manifest(output, "val.txt", validation_paths)

    train_grid = grid_records(
        split_ids["train"], train_paths, train_sizes, annotations,
        args.tile_size, args.tile_overlap, args.min_visible,
    )
    selected_grid = select_training_grid(train_grid, args.negative_ratio, args.seed)
    grid_paths, grid_stats = write_yolo_records(
        output / "grid", selected_grid, args.tile_size
    )

    ratios: dict[str, object] = {}
    for ratio in args.centered_ratios:
        name = ratio_name(ratio)
        max_per_image = (
            args.max_centered_per_image
            if ratio <= min(args.centered_ratios)
            else args.high_ratio_max_centered_per_image
        )
        centered, quotas = centered_records(
            split_ids["train"], train_paths, train_sizes, annotations, train_grid,
            args.tile_size, args.min_visible, ratio, args.center_jitter,
            args.anchor_min_visible, max_per_image, args.seed,
        )
        centered_paths, centered_stats = write_yolo_records(
            output / name, centered, args.tile_size
        )
        train_manifest = write_manifest(output, f"train_{name}.txt", grid_paths + centered_paths)
        yaml_path = output / f"dataset_{name}.yaml"
        yaml_path.write_text(
            f"train: {train_manifest.name}\n"
            f"val: {validation_manifest.name}\n"
            "names:\n" + "".join(f"  {i}: {name}\n" for i, name in enumerate(CLASS_NAMES))
        )
        ratios[name] = {
            "centered_ratio": ratio,
            "max_centered_per_image": max_per_image,
            "centered_crop_quotas": quotas,
            "centered_tiles": centered_stats,
            "total_train_images": len(grid_paths) + len(centered_paths),
            "train_manifest_sha256": sha256_file(train_manifest),
            "dataset_yaml": yaml_path.name,
        }

    marker = {
        "name": "yolo26-s-p2-scene-holdout-v2-sliced-pilots",
        "classes": list(CLASS_NAMES),
        "train_images": len(split_ids["train"]),
        "validation_images": len(split_ids["valid"]),
        "deduplicated_annotation_rows": duplicate_rows,
        "source_hashes": {
            "annotations.csv": sha256_file(annotation_path),
            "train.txt": sha256_file(manifests["train"]),
            "val.txt": sha256_file(manifests["valid"]),
            "val_strata.csv": sha256_file(split_dir / "val_strata.csv"),
        },
        "parameters": {
            "tile_size": args.tile_size,
            "tile_overlap": args.tile_overlap,
            "min_visible": args.min_visible,
            "negative_ratio": args.negative_ratio,
            "center_jitter": args.center_jitter,
            "anchor_min_visible": args.anchor_min_visible,
            "max_centered_per_image": args.max_centered_per_image,
            "high_ratio_max_centered_per_image": args.high_ratio_max_centered_per_image,
            "seed": args.seed,
            "focus_shares": {"van": 0.55, "truck": 0.30, "bus": 0.15},
        },
        "base_train_grid": {
            "images": len(train_grid),
            "positive_images": sum(bool(record["boxes"]) for record in train_grid),
            "negative_images": sum(not record["boxes"] for record in train_grid),
        },
        "selected_grid": grid_stats,
        "validation": validation_stats,
        "ratios": ratios,
    }
    (output / "READY.json").write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n")
    print(json.dumps(marker, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
