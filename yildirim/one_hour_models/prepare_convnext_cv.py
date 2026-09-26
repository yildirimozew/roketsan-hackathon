#!/usr/bin/env python3
"""Create deterministic car/van crops from the fixed scene split."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from convnext_cv_common import CLASS_NAMES, dev_group, object_crop, sha256
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context", type=float, default=1.75)
    parser.add_argument("--size", type=int, default=224)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--dataset-name", default="convnext-tiny-car-van-scene-holdout-v1")
    return parser.parse_args()


def read_ids(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def crop_tree_hash(root: Path, records: list[dict[str, str | int | float]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        relative = str(record["path"])
        digest.update(relative.encode())
        with (root / relative).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def prepare_image(task: tuple) -> tuple[str, list[dict[str, str | int | float]]]:
    image_id, image_path, destination, rows, scene_group, subset, context, size = task
    records = []
    with Image.open(image_path) as source:
        source = source.convert("RGB")
        for row in rows:
            box = [float(row[key]) for key in ("x", "y", "w", "h")]
            crop = object_crop(source, box, context, size)
            file_name = f"{image_id}__a{row['annotation_index']}.jpg"
            crop.save(destination / file_name, quality=95, subsampling=0, optimize=False)
            records.append(
                {
                    "path": f"crops/{subset}/{file_name}",
                    "image_id": image_id,
                    "scene_group": scene_group,
                    "label": row["label"],
                    "target": CLASS_NAMES.index(row["label"]),
                    "x": box[0],
                    "y": box[1],
                    "w": box[2],
                    "h": box[3],
                }
            )
    return subset, records


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    train_ids = read_ids(args.split / "train.txt")
    val_ids = read_ids(args.split / "val.txt")
    if train_ids & val_ids:
        raise ValueError("fixed train and validation image IDs overlap")

    groups: dict[str, tuple[str, str]] = {}
    with (args.split / "groups.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            groups[row["image_id"]] = (row["scene_group"], row["split"])
    if set(groups) != train_ids | val_ids:
        raise ValueError("groups.csv membership differs from fixed split manifests")

    rows_by_image: dict[str, list[dict[str, str]]] = {}
    with args.annotations.open(newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            if row["label"] not in CLASS_NAMES:
                continue
            if float(row["w"]) * float(row["h"]) < 200:
                continue
            row["annotation_index"] = str(index)
            rows_by_image.setdefault(row["image_id"], []).append(row)

    manifests: dict[str, list[dict[str, str | int | float]]] = {
        "train": [],
        "dev": [],
        "fixed_val": [],
    }
    tasks = []
    for image_id in sorted(rows_by_image):
        if image_id not in groups:
            continue
        scene_group, fixed_split = groups[image_id]
        subset = "fixed_val" if fixed_split == "val" else (
            "dev" if dev_group(scene_group, args.seed) else "train"
        )
        image_path = args.images / f"{image_id}.jpg"
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        destination = args.output / "crops" / subset
        destination.mkdir(parents=True, exist_ok=True)
        tasks.append(
            (
                image_id,
                image_path,
                destination,
                rows_by_image[image_id],
                scene_group,
                subset,
                args.context,
                args.size,
            )
        )

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        results = executor.map(prepare_image, tasks, chunksize=4)
        for image_number, (subset, records) in enumerate(results, start=1):
            manifests[subset].extend(records)
            if image_number % 250 == 0:
                print(f"prepared {image_number}/{len(tasks)} source images", flush=True)

    fields = ("path", "image_id", "scene_group", "label", "target", "x", "y", "w", "h")
    manifest_hashes = {}
    crop_hashes = {}
    counts = {}
    scenes = {}
    for subset, records in manifests.items():
        manifest = args.output / f"{subset}.csv"
        with manifest.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
        manifest_hashes[manifest.name] = sha256(manifest)
        crop_hashes[subset] = crop_tree_hash(args.output, records)
        counts[subset] = dict(Counter(str(record["label"]) for record in records))
        scenes[subset] = sorted({str(record["scene_group"]) for record in records})

    train_scenes = {str(record["scene_group"]) for record in manifests["train"]}
    dev_scenes = {str(record["scene_group"]) for record in manifests["dev"]}
    val_scenes = {str(record["scene_group"]) for record in manifests["fixed_val"]}
    if train_scenes & dev_scenes or train_scenes & val_scenes or dev_scenes & val_scenes:
        raise ValueError("classifier subsets have scene leakage")

    ready = {
        "name": args.dataset_name,
        "parameters": {
            "context": args.context,
            "size": args.size,
            "seed": args.seed,
            "min_area": 200,
            "development_scene_rule": "sha256(seed:scene_group) uint64 modulo 10 equals 0",
            "development_scene_fraction": 0.1,
            "padding_rgb": [round(value * 255) for value in (0.485, 0.456, 0.406)],
            "resize_interpolation": "bicubic",
            "jpeg_quality": 95,
            "jpeg_subsampling": 0,
        },
        "source_hashes": {
            "annotations.csv": sha256(args.annotations),
            "groups.csv": sha256(args.split / "groups.csv"),
            "train.txt": sha256(args.split / "train.txt"),
            "val.txt": sha256(args.split / "val.txt"),
        },
        "manifest_hashes": manifest_hashes,
        "crop_tree_sha256": crop_hashes,
        "crop_counts": counts,
        "scene_counts": {subset: len(values) for subset, values in scenes.items()},
        "scene_membership": scenes,
        "scene_overlap": 0,
    }
    (args.output / "READY.json").write_text(json.dumps(ready, indent=2, sort_keys=True) + "\n")
    print(json.dumps(ready, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
