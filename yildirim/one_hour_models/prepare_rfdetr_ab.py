#!/usr/bin/env python3
"""Prepare the matched RF-DETR scene-holdout A/B dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image


CLASS_NAMES = ("car", "van", "truck", "bus")
CLASS_TO_ID = {name: index for index, name in enumerate(CLASS_NAMES)}
FOCUS_SHARES = {"van": 0.55, "truck": 0.30, "bus": 0.15}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-dir", type=Path, required=True)
    parser.add_argument("--tile-size", type=int, default=704)
    parser.add_argument("--tile-overlap", type=float, default=0.25)
    parser.add_argument("--min-visible", type=float, default=0.60)
    parser.add_argument("--negative-ratio", type=float, default=0.20)
    parser.add_argument("--centered-ratio", type=float, default=0.25)
    parser.add_argument("--center-jitter", type=float, default=0.15)
    parser.add_argument("--anchor-min-visible", type=float, default=0.80)
    parser.add_argument("--max-centered-per-image", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hex(*parts: object) -> str:
    return hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()


def stable_unit(*parts: object) -> float:
    return int(stable_hex(*parts)[:16], 16) / float(16**16 - 1)


def read_ids(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def read_annotations(path: Path) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = defaultdict(list)
    with path.open(newline="") as handle:
        for annotation_id, row in enumerate(csv.DictReader(handle), start=1):
            result[row["image_id"]].append(
                {
                    "annotation_id": annotation_id,
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "w": float(row["w"]),
                    "h": float(row["h"]),
                    "label": row["label"],
                }
            )
    return result


def image_path(images_dir: Path, image_id: str) -> Path:
    for suffix in (".jpg", ".jpeg", ".JPG", ".JPEG", ".png"):
        candidate = images_dir / f"{image_id}{suffix}"
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"No image found for {image_id} in {images_dir}")


def categories() -> list[dict[str, object]]:
    return [
        {"id": index, "name": name, "supercategory": "vehicle"}
        for index, name in enumerate(CLASS_NAMES)
    ]


def tile_origins(length: int, tile_size: int, step: int) -> list[int]:
    if length <= tile_size:
        return [0]
    origins = list(range(0, length - tile_size + 1, step))
    if origins[-1] != length - tile_size:
        origins.append(length - tile_size)
    return origins


def clipped_box(
    box: dict[str, object], left: int, top: int, size: int, min_visible: float
) -> list[float] | None:
    x1, y1 = float(box["x"]), float(box["y"])
    x2, y2 = x1 + float(box["w"]), y1 + float(box["h"])
    ix1, iy1 = max(x1, left), max(y1, top)
    ix2, iy2 = min(x2, left + size), min(y2, top + size)
    if ix2 <= ix1 or iy2 <= iy1:
        return None
    visible = (ix2 - ix1) * (iy2 - iy1)
    if visible / max(1.0, float(box["w"]) * float(box["h"])) < min_visible:
        return None
    return [ix1 - left, iy1 - top, ix2 - ix1, iy2 - iy1]


def image_sizes(images_dir: Path, ids: list[str]) -> tuple[dict[str, Path], dict[str, tuple[int, int]]]:
    paths: dict[str, Path] = {}
    sizes: dict[str, tuple[int, int]] = {}
    for image_id in ids:
        source = image_path(images_dir, image_id)
        with Image.open(source) as image:
            sizes[image_id] = image.size
        paths[image_id] = source
    return paths, sizes


def record_boxes(
    annotations: dict[str, list[dict[str, object]]],
    image_id: str,
    left: int,
    top: int,
    tile_size: int,
    min_visible: float,
) -> list[tuple[dict[str, object], list[float]]]:
    result = []
    for box in annotations.get(image_id, []):
        clipped = clipped_box(box, left, top, tile_size, min_visible)
        if clipped is not None:
            result.append((box, clipped))
    return result


def grid_records(
    ids: list[str],
    paths: dict[str, Path],
    sizes: dict[str, tuple[int, int]],
    annotations: dict[str, list[dict[str, object]]],
    tile_size: int,
    overlap: float,
    min_visible: float,
) -> list[dict[str, object]]:
    step = max(1, round(tile_size * (1 - overlap)))
    result = []
    for image_id in ids:
        width, height = sizes[image_id]
        for top in tile_origins(height, tile_size, step):
            for left in tile_origins(width, tile_size, step):
                result.append(
                    {
                        "source": paths[image_id],
                        "image_id": image_id,
                        "left": left,
                        "top": top,
                        "boxes": record_boxes(
                            annotations, image_id, left, top, tile_size, min_visible
                        ),
                        "kind": "grid",
                        "focus_class": None,
                        "focus_annotation_id": None,
                    }
                )
    return result


def crop_origin(
    box: dict[str, object],
    width: int,
    height: int,
    tile_size: int,
    jitter: float,
    seed: int,
    attempt: int,
) -> tuple[int, int]:
    dx = (stable_unit(seed, box["annotation_id"], attempt, "x") * 2 - 1) * jitter * tile_size
    dy = (stable_unit(seed, box["annotation_id"], attempt, "y") * 2 - 1) * jitter * tile_size
    center_x = float(box["x"]) + float(box["w"]) / 2 + dx
    center_y = float(box["y"]) + float(box["h"]) / 2 + dy
    left = round(min(max(0.0, center_x - tile_size / 2), max(0, width - tile_size)))
    top = round(min(max(0.0, center_y - tile_size / 2), max(0, height - tile_size)))
    return left, top


def van_has_nearby_car(
    box: dict[str, object],
    image_id: str,
    size: tuple[int, int],
    annotations: dict[str, list[dict[str, object]]],
    tile_size: int,
) -> bool:
    width, height = size
    left, top = crop_origin(box, width, height, tile_size, 0.0, 0, 0)
    return any(
        other["label"] == "car" and clipped_box(other, left, top, tile_size, 0.60) is not None
        for other in annotations.get(image_id, [])
    )


def integer_quotas(total: int) -> dict[str, int]:
    raw = {name: total * share for name, share in FOCUS_SHARES.items()}
    quotas = {name: math.floor(value) for name, value in raw.items()}
    remainder = total - sum(quotas.values())
    order = sorted(FOCUS_SHARES, key=lambda name: (-(raw[name] - quotas[name]), list(FOCUS_SHARES).index(name)))
    for name in order[:remainder]:
        quotas[name] += 1
    return quotas


def centered_records(
    ids: list[str],
    paths: dict[str, Path],
    sizes: dict[str, tuple[int, int]],
    annotations: dict[str, list[dict[str, object]]],
    base_records: list[dict[str, object]],
    tile_size: int,
    min_visible: float,
    ratio: float,
    jitter: float,
    anchor_min_visible: float,
    max_per_image: int,
    seed: int,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    positives = sum(bool(record["boxes"]) for record in base_records)
    quotas = integer_quotas(round(positives * ratio))
    allowed_ids = set(ids)
    used_origins = {
        (str(record["image_id"]), int(record["left"]), int(record["top"]))
        for record in base_records
    }
    per_image: Counter[str] = Counter()
    selected = []

    for focus_class, quota in quotas.items():
        candidates = []
        for image_id in ids:
            for box in annotations.get(image_id, []):
                if box["label"] != focus_class:
                    continue
                preferred = focus_class == "van" and van_has_nearby_car(
                    box, image_id, sizes[image_id], annotations, tile_size
                )
                candidates.append((not preferred, stable_hex(seed, focus_class, image_id, box["annotation_id"]), image_id, box))
        candidates.sort(key=lambda value: (value[0], value[1]))

        accepted = 0
        for _, _, image_id, anchor in candidates:
            if accepted >= quota:
                break
            if image_id not in allowed_ids or per_image[image_id] >= max_per_image:
                continue
            width, height = sizes[image_id]
            chosen: tuple[int, int] | None = None
            for attempt in range(10):
                left, top = crop_origin(anchor, width, height, tile_size, jitter, seed, attempt)
                key = (image_id, left, top)
                if key in used_origins:
                    continue
                if clipped_box(anchor, left, top, tile_size, anchor_min_visible) is not None:
                    chosen = (left, top)
                    break
            if chosen is None:
                continue
            left, top = chosen
            boxes = record_boxes(annotations, image_id, left, top, tile_size, min_visible)
            selected.append(
                {
                    "source": paths[image_id],
                    "image_id": image_id,
                    "left": left,
                    "top": top,
                    "boxes": boxes,
                    "kind": "centered",
                    "focus_class": focus_class,
                    "focus_annotation_id": int(anchor["annotation_id"]),
                }
            )
            used_origins.add((image_id, left, top))
            per_image[image_id] += 1
            accepted += 1
        if accepted != quota:
            raise RuntimeError(f"Could only create {accepted}/{quota} centered {focus_class} crops")
    return selected, quotas


def select_training_grid(records: list[dict[str, object]], negative_ratio: float, seed: int) -> list[dict[str, object]]:
    positives = [record for record in records if record["boxes"]]
    negatives = [record for record in records if not record["boxes"]]
    negatives.sort(
        key=lambda record: stable_hex(seed, record["image_id"], record["left"], record["top"], "negative")
    )
    keep = min(len(negatives), round(len(positives) * negative_ratio))
    return positives + negatives[:keep]


def write_original_coco(
    output: Path,
    split: str,
    ids: list[str],
    paths: dict[str, Path],
    sizes: dict[str, tuple[int, int]],
    annotations: dict[str, list[dict[str, object]]],
) -> None:
    split_dir = output / split
    split_dir.mkdir(parents=True, exist_ok=False)
    images = []
    coco_annotations = []
    annotation_id = 1
    for numeric_id, image_id in enumerate(ids, start=1):
        source = paths[image_id]
        (split_dir / source.name).symlink_to(source)
        width, height = sizes[image_id]
        images.append(
            {"id": numeric_id, "file_name": source.name, "width": width, "height": height, "original_image_id": image_id}
        )
        for box in annotations.get(image_id, []):
            coco_annotations.append(
                {
                    "id": annotation_id,
                    "image_id": numeric_id,
                    "category_id": CLASS_TO_ID[str(box["label"])],
                    "bbox": [float(box["x"]), float(box["y"]), float(box["w"]), float(box["h"])],
                    "area": float(box["w"]) * float(box["h"]),
                    "iscrowd": 0,
                }
            )
            annotation_id += 1
    payload = {
        "info": {"description": f"Roketsan scene_holdout_v1 original {split}"},
        "licenses": [],
        "images": images,
        "annotations": coco_annotations,
        "categories": categories(),
    }
    (split_dir / "_annotations.coco.json").write_text(json.dumps(payload))


def write_tiles(output: Path, split: str, records: list[dict[str, object]], tile_size: int) -> dict[str, object]:
    split_dir = output / split
    split_dir.mkdir(parents=True, exist_ok=False)
    records.sort(
        key=lambda record: (
            str(record["image_id"]),
            str(record["kind"]),
            int(record["top"]),
            int(record["left"]),
            int(record["focus_annotation_id"] or 0),
        )
    )
    images = []
    coco_annotations = []
    class_counts: Counter[str] = Counter()
    annotation_id = 1
    opened_source: Path | None = None
    opened_image: Image.Image | None = None
    try:
        for numeric_id, record in enumerate(records, start=1):
            source = Path(record["source"])
            if source != opened_source:
                if opened_image is not None:
                    opened_image.close()
                opened_image = Image.open(source).convert("RGB")
                opened_source = source
            left, top = int(record["left"]), int(record["top"])
            if record["kind"] == "centered":
                suffix = f"focus-{record['focus_class']}-a{record['focus_annotation_id']}"
            else:
                suffix = "grid"
            file_name = f"{record['image_id']}__{suffix}_x{left}_y{top}.jpg"
            assert opened_image is not None
            crop = opened_image.crop((left, top, left + tile_size, top + tile_size))
            if crop.size != (tile_size, tile_size):
                padded = Image.new("RGB", (tile_size, tile_size))
                padded.paste(crop, (0, 0))
                crop = padded
            crop.save(split_dir / file_name, quality=92, optimize=False)
            image_record = {
                "id": numeric_id,
                "file_name": file_name,
                "width": tile_size,
                "height": tile_size,
                "original_image_id": record["image_id"],
                "tile_x": left,
                "tile_y": top,
                "crop_kind": record["kind"],
            }
            if record["focus_class"] is not None:
                image_record["focus_class"] = record["focus_class"]
                image_record["focus_annotation_id"] = record["focus_annotation_id"]
            images.append(image_record)
            for box, clipped in record["boxes"]:
                width, height = float(clipped[2]), float(clipped[3])
                label = str(box["label"])
                class_counts[label] += 1
                coco_annotations.append(
                    {
                        "id": annotation_id,
                        "image_id": numeric_id,
                        "category_id": CLASS_TO_ID[label],
                        "bbox": [float(value) for value in clipped],
                        "area": width * height,
                        "iscrowd": 0,
                    }
                )
                annotation_id += 1
    finally:
        if opened_image is not None:
            opened_image.close()
    payload = {
        "info": {"description": f"Roketsan scene_holdout_v1 RF-DETR {split} tiles"},
        "licenses": [],
        "images": images,
        "annotations": coco_annotations,
        "categories": categories(),
    }
    annotation_path = split_dir / "_annotations.coco.json"
    annotation_path.write_text(json.dumps(payload))
    return {
        "images": len(images),
        "positive_images": sum(bool(record["boxes"]) for record in records),
        "negative_images": sum(not record["boxes"] for record in records),
        "centered_images": sum(record["kind"] == "centered" for record in records),
        "annotations": len(coco_annotations),
        "annotation_class_counts": {name: class_counts[name] for name in CLASS_NAMES},
        "annotations_sha256": sha256_file(annotation_path),
    }


def main() -> None:
    args = parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    split_dir = args.split_dir.resolve()
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
        raise ValueError("Unexpected scene_holdout_v1 split sizes")

    annotations = read_annotations(annotation_path)
    all_ids = split_ids["train"] + split_ids["valid"]
    paths, sizes = image_sizes(images_dir, all_ids)
    train_paths = {image_id: paths[image_id] for image_id in split_ids["train"]}
    train_sizes = {image_id: sizes[image_id] for image_id in split_ids["train"]}
    valid_paths = {image_id: paths[image_id] for image_id in split_ids["valid"]}
    valid_sizes = {image_id: sizes[image_id] for image_id in split_ids["valid"]}

    write_original_coco(output / "coco", "train", split_ids["train"], train_paths, train_sizes, annotations)
    write_original_coco(output / "coco", "valid", split_ids["valid"], valid_paths, valid_sizes, annotations)

    train_grid = grid_records(
        split_ids["train"], train_paths, train_sizes, annotations,
        args.tile_size, args.tile_overlap, args.min_visible,
    )
    selected_grid = select_training_grid(train_grid, args.negative_ratio, args.seed)
    centered, quotas = centered_records(
        split_ids["train"], train_paths, train_sizes, annotations, train_grid,
        args.tile_size, args.min_visible, args.centered_ratio, args.center_jitter,
        args.anchor_min_visible, args.max_centered_per_image, args.seed,
    )
    valid_grid = grid_records(
        split_ids["valid"], valid_paths, valid_sizes, annotations,
        args.tile_size, args.tile_overlap, args.min_visible,
    )
    train_stats = write_tiles(output / "rfdetr_tiles", "train", selected_grid + centered, args.tile_size)
    valid_stats = write_tiles(output / "rfdetr_tiles", "valid", valid_grid, args.tile_size)

    marker = {
        "name": "rfdetr-scene-holdout-v1-ab",
        "classes": list(CLASS_NAMES),
        "train_images": len(split_ids["train"]),
        "validation_images": len(split_ids["valid"]),
        "source_hashes": {
            "annotations.csv": sha256_file(annotation_path),
            "train.txt": sha256_file(manifests["train"]),
            "val.txt": sha256_file(manifests["valid"]),
        },
        "parameters": {
            "tile_size": args.tile_size,
            "tile_overlap": args.tile_overlap,
            "min_visible": args.min_visible,
            "negative_ratio": args.negative_ratio,
            "centered_ratio": args.centered_ratio,
            "center_jitter": args.center_jitter,
            "anchor_min_visible": args.anchor_min_visible,
            "max_centered_per_image": args.max_centered_per_image,
            "seed": args.seed,
            "focus_shares": FOCUS_SHARES,
        },
        "base_train_grid": {
            "images": len(train_grid),
            "positive_images": sum(bool(record["boxes"]) for record in train_grid),
            "negative_images": sum(not record["boxes"] for record in train_grid),
        },
        "centered_crop_quotas": quotas,
        "train_tiles": train_stats,
        "validation_tiles": valid_stats,
    }
    (output / "READY.json").write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n")
    print(json.dumps(marker, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
