#!/usr/bin/env python3
"""Create a reproducible, class-aware train/validation image split."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, default=Path("data/train/images"))
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path("data/train/annotations.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path("splits"))
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_inputs(images_dir: Path, annotations_path: Path):
    image_ids = sorted(path.stem for path in images_dir.glob("*.jpg"))
    if not image_ids:
        raise ValueError(f"No JPG images found in {images_dir}")
    if len(image_ids) != len(set(image_ids)):
        raise ValueError("Duplicate image stems found")

    labels_by_image: dict[str, set[str]] = defaultdict(set)
    box_counts: Counter[str] = Counter()
    with annotations_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"image_id", "label"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Annotations must contain columns: {sorted(required)}")
        for row in reader:
            labels_by_image[row["image_id"]].add(row["label"])
            box_counts[row["label"]] += 1

    missing = sorted(set(labels_by_image) - set(image_ids))
    if missing:
        raise ValueError(f"{len(missing)} annotated image IDs have no JPG file")
    return image_ids, labels_by_image, box_counts


def stratified_split(image_ids, labels_by_image, val_fraction: float, seed: int):
    if not 0 < val_fraction < 1:
        raise ValueError("--val-fraction must be between 0 and 1")

    # Group by the complete set of classes present in each image. This retains
    # multi-class combinations and background-only images in both partitions.
    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for image_id in image_ids:
        groups[tuple(sorted(labels_by_image.get(image_id, set())))].append(image_id)

    target_val = round(len(image_ids) * val_fraction)
    quotas = {signature: int(len(ids) * val_fraction) for signature, ids in groups.items()}
    remaining = target_val - sum(quotas.values())
    remainders = sorted(
        groups,
        key=lambda signature: (
            -(len(groups[signature]) * val_fraction % 1),
            signature,
        ),
    )
    for signature in remainders[:remaining]:
        quotas[signature] += 1

    rng = random.Random(seed)
    train_ids: list[str] = []
    val_ids: list[str] = []
    for signature in sorted(groups):
        ids = sorted(groups[signature])
        rng.shuffle(ids)
        val_count = quotas[signature]
        val_ids.extend(ids[:val_count])
        train_ids.extend(ids[val_count:])

    return sorted(train_ids), sorted(val_ids)


def class_presence(ids, labels_by_image):
    counts: Counter[str] = Counter()
    for image_id in ids:
        labels = labels_by_image.get(image_id, set())
        if not labels:
            counts["background"] += 1
        counts.update(labels)
    return dict(sorted(counts.items()))


def write_lines(path: Path, values: list[str]) -> None:
    path.write_text("".join(f"{value}\n" for value in values))


def main() -> None:
    args = parse_args()
    image_ids, labels_by_image, box_counts = read_inputs(args.images, args.annotations)
    train_ids, val_ids = stratified_split(
        image_ids, labels_by_image, args.val_fraction, args.seed
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_lines(args.output / "train.txt", train_ids)
    write_lines(args.output / "val.txt", val_ids)

    metadata = {
        "seed": args.seed,
        "validation_fraction": args.val_fraction,
        "strategy": "stratified by image-level class combination",
        "annotations_sha256": file_sha256(args.annotations),
        "total_images": len(image_ids),
        "train_images": len(train_ids),
        "validation_images": len(val_ids),
        "annotation_box_counts": dict(sorted(box_counts.items())),
        "train_image_class_presence": class_presence(train_ids, labels_by_image),
        "validation_image_class_presence": class_presence(val_ids, labels_by_image),
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
