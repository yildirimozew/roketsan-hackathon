#!/usr/bin/env python3
"""Create reproducible YOLO/COCO datasets for the five one-hour pilots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

from PIL import Image


CLASS_NAMES = ("car", "van", "truck", "bus")
CLASS_TO_ID = {name: index for index, name in enumerate(CLASS_NAMES)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tile-size", type=int, default=704)
    parser.add_argument("--tile-overlap", type=float, default=0.25)
    parser.add_argument("--min-visible", type=float, default=0.60)
    parser.add_argument("--negative-ratio", type=float, default=0.20)
    return parser.parse_args()


def read_ids(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def read_annotations(path: Path) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = defaultdict(list)
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            result[row["image_id"]].append(
                {
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "w": float(row["w"]),
                    "h": float(row["h"]),
                    "label": row["label"],
                }
            )
    return result


def image_path(images: Path, image_id: str) -> Path:
    for suffix in (".jpg", ".jpeg", ".JPG", ".JPEG", ".png"):
        candidate = images / f"{image_id}{suffix}"
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"No image found for {image_id} in {images}")


def replace_symlink(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or destination.exists():
        destination.unlink()
    destination.symlink_to(source)


def categories() -> list[dict[str, object]]:
    return [
        {"id": index, "name": name, "supercategory": "vehicle"}
        for index, name in enumerate(CLASS_NAMES)
    ]


def write_yolo(
    output: Path,
    images_dir: Path,
    split_ids: dict[str, list[str]],
    annotations: dict[str, list[dict[str, object]]],
) -> None:
    for split, ids in split_ids.items():
        for image_id in ids:
            source = image_path(images_dir, image_id)
            with Image.open(source) as image:
                width, height = image.size
            replace_symlink(source, output / "images" / split / source.name)
            lines = []
            for box in annotations.get(image_id, []):
                x = float(box["x"])
                y = float(box["y"])
                w = float(box["w"])
                h = float(box["h"])
                cx = (x + w / 2) / width
                cy = (y + h / 2) / height
                lines.append(
                    f"{CLASS_TO_ID[str(box['label'])]} {cx:.8f} {cy:.8f} "
                    f"{w / width:.8f} {h / height:.8f}"
                )
            label_path = output / "labels" / split / f"{image_id}.txt"
            label_path.parent.mkdir(parents=True, exist_ok=True)
            label_path.write_text("\n".join(lines) + ("\n" if lines else ""))

    yaml_text = (
        f"path: {output.resolve()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        + "".join(f"  {index}: {name}\n" for index, name in enumerate(CLASS_NAMES))
    )
    (output / "dataset.yaml").write_text(yaml_text)


def write_coco_split(
    output: Path,
    split: str,
    ids: list[str],
    images_dir: Path,
    annotations: dict[str, list[dict[str, object]]],
) -> None:
    split_dir = output / split
    split_dir.mkdir(parents=True, exist_ok=True)
    coco_images: list[dict[str, object]] = []
    coco_annotations: list[dict[str, object]] = []
    ann_id = 1
    for numeric_id, image_id in enumerate(ids, start=1):
        source = image_path(images_dir, image_id)
        with Image.open(source) as image:
            width, height = image.size
        replace_symlink(source, split_dir / source.name)
        coco_images.append(
            {
                "id": numeric_id,
                "file_name": source.name,
                "width": width,
                "height": height,
                "original_image_id": image_id,
            }
        )
        for box in annotations.get(image_id, []):
            w = float(box["w"])
            h = float(box["h"])
            coco_annotations.append(
                {
                    "id": ann_id,
                    "image_id": numeric_id,
                    "category_id": CLASS_TO_ID[str(box["label"])],
                    "bbox": [float(box["x"]), float(box["y"]), w, h],
                    "area": w * h,
                    "iscrowd": 0,
                }
            )
            ann_id += 1
    payload = {
        "info": {"description": "Roketsan vehicle detection Fold 1"},
        "licenses": [],
        "images": coco_images,
        "annotations": coco_annotations,
        "categories": categories(),
    }
    (split_dir / "_annotations.coco.json").write_text(json.dumps(payload))


def tile_origins(length: int, tile_size: int, step: int) -> list[int]:
    if length <= tile_size:
        return [0]
    origins = list(range(0, length - tile_size + 1, step))
    if origins[-1] != length - tile_size:
        origins.append(length - tile_size)
    return origins


def visible_box(
    box: dict[str, object], left: int, top: int, size: int, min_visible: float
) -> list[float] | None:
    x1 = float(box["x"])
    y1 = float(box["y"])
    x2 = x1 + float(box["w"])
    y2 = y1 + float(box["h"])
    ix1 = max(x1, left)
    iy1 = max(y1, top)
    ix2 = min(x2, left + size)
    iy2 = min(y2, top + size)
    if ix2 <= ix1 or iy2 <= iy1:
        return None
    visible = (ix2 - ix1) * (iy2 - iy1)
    original = max(1.0, (x2 - x1) * (y2 - y1))
    if visible / original < min_visible:
        return None
    return [ix1 - left, iy1 - top, ix2 - ix1, iy2 - iy1]


def write_tiled_coco_split(
    output: Path,
    split: str,
    ids: list[str],
    images_dir: Path,
    annotations: dict[str, list[dict[str, object]]],
    tile_size: int,
    overlap: float,
    min_visible: float,
    negative_ratio: float,
) -> None:
    step = max(1, round(tile_size * (1 - overlap)))
    records: list[dict[str, object]] = []
    for image_id in ids:
        source = image_path(images_dir, image_id)
        with Image.open(source) as image:
            width, height = image.size
        for top in tile_origins(height, tile_size, step):
            for left in tile_origins(width, tile_size, step):
                tile_boxes = []
                for box in annotations.get(image_id, []):
                    clipped = visible_box(box, left, top, tile_size, min_visible)
                    if clipped is not None:
                        tile_boxes.append((box, clipped))
                records.append(
                    {
                        "source": source,
                        "image_id": image_id,
                        "left": left,
                        "top": top,
                        "boxes": tile_boxes,
                    }
                )

    positives = [record for record in records if record["boxes"]]
    negatives = [record for record in records if not record["boxes"]]
    negatives.sort(
        key=lambda record: hashlib.sha256(
            f"{record['image_id']}:{record['left']}:{record['top']}".encode()
        ).hexdigest()
    )
    keep_negative = min(len(negatives), round(len(positives) * negative_ratio))
    selected = positives + negatives[:keep_negative]
    selected.sort(key=lambda record: (str(record["image_id"]), int(record["top"]), int(record["left"])))

    split_dir = output / split
    split_dir.mkdir(parents=True, exist_ok=True)
    coco_images: list[dict[str, object]] = []
    coco_annotations: list[dict[str, object]] = []
    ann_id = 1
    open_source: Path | None = None
    opened_image: Image.Image | None = None
    try:
        for numeric_id, record in enumerate(selected, start=1):
            source = Path(record["source"])
            if source != open_source:
                if opened_image is not None:
                    opened_image.close()
                opened_image = Image.open(source).convert("RGB")
                open_source = source
            left = int(record["left"])
            top = int(record["top"])
            file_name = f"{record['image_id']}__x{left}_y{top}.jpg"
            assert opened_image is not None
            crop = opened_image.crop((left, top, left + tile_size, top + tile_size))
            if crop.size != (tile_size, tile_size):
                padded = Image.new("RGB", (tile_size, tile_size))
                padded.paste(crop, (0, 0))
                crop = padded
            crop.save(split_dir / file_name, quality=92, optimize=False)
            coco_images.append(
                {
                    "id": numeric_id,
                    "file_name": file_name,
                    "width": tile_size,
                    "height": tile_size,
                    "original_image_id": record["image_id"],
                    "tile_x": left,
                    "tile_y": top,
                }
            )
            for box, clipped in record["boxes"]:
                w, h = float(clipped[2]), float(clipped[3])
                coco_annotations.append(
                    {
                        "id": ann_id,
                        "image_id": numeric_id,
                        "category_id": CLASS_TO_ID[str(box["label"])],
                        "bbox": [float(value) for value in clipped],
                        "area": w * h,
                        "iscrowd": 0,
                    }
                )
                ann_id += 1
    finally:
        if opened_image is not None:
            opened_image.close()

    payload = {
        "info": {"description": "Roketsan vehicle detection 704px tiles"},
        "licenses": [],
        "images": coco_images,
        "annotations": coco_annotations,
        "categories": categories(),
    }
    (split_dir / "_annotations.coco.json").write_text(json.dumps(payload))


def main() -> None:
    args = parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    images_dir = repo / "data" / "train" / "images"
    annotations = read_annotations(repo / "data" / "train" / "annotations.csv")
    split_ids = {
        "train": read_ids(repo / "splits" / "folds" / "fold_1_train.txt"),
        "val": read_ids(repo / "splits" / "folds" / "fold_1_val.txt"),
    }
    write_yolo(output / "yolo", images_dir, split_ids, annotations)
    write_coco_split(output / "coco", "train", split_ids["train"], images_dir, annotations)
    write_coco_split(output / "coco", "valid", split_ids["val"], images_dir, annotations)
    write_tiled_coco_split(
        output / "rfdetr_tiles",
        "train",
        split_ids["train"],
        images_dir,
        annotations,
        args.tile_size,
        args.tile_overlap,
        args.min_visible,
        args.negative_ratio,
    )
    write_tiled_coco_split(
        output / "rfdetr_tiles",
        "valid",
        split_ids["val"],
        images_dir,
        annotations,
        args.tile_size,
        args.tile_overlap,
        args.min_visible,
        args.negative_ratio,
    )
    marker = {
        "classes": list(CLASS_NAMES),
        "train_images": len(split_ids["train"]),
        "validation_images": len(split_ids["val"]),
        "tile_size": args.tile_size,
        "tile_overlap": args.tile_overlap,
        "min_visible": args.min_visible,
    }
    (output / "READY.json").write_text(json.dumps(marker, indent=2) + "\n")
    print(json.dumps(marker, indent=2))


if __name__ == "__main__":
    main()
