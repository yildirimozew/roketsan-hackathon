#!/usr/bin/env python3
"""Fail-fast integrity checks for the RF-DETR scene-holdout A/B datasets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


ANNOTATIONS_SHA256 = "c946f29a627438bc4567544cc654234df2eab6a8e342a9ee4d9a6fd997e857ce"
EXPECTED_HASHES = {
    "rfdetr-scene-holdout-v1-ab": {
        "annotations.csv": ANNOTATIONS_SHA256,
        "train.txt": "f4cc66110bc17ba00bbbadb21de55c7f906d5bc505c1cfcbb49833cb2b148678",
        "val.txt": "c0ddf4ef726abebd8687a02ea036b0ec79947d801070ba9d03cb7b6849586029",
    },
    "rfdetr-scene-holdout-v2-ab": {
        "annotations.csv": ANNOTATIONS_SHA256,
        "train.txt": "c544705973b00df50c0f3c13373b1430bd780b14ef0c8c8fb02c26a817cff4a1",
        "val.txt": "35b881a4c14fd8e61f09ddeabc440f595d16962b3cf9c680f4042c024f076c1e",
    },
    "rfdetr-full-train-v1-ab": {
        "annotations.csv": ANNOTATIONS_SHA256,
        "train.txt": "f4cc66110bc17ba00bbbadb21de55c7f906d5bc505c1cfcbb49833cb2b148678",
        "val.txt": "c0ddf4ef726abebd8687a02ea036b0ec79947d801070ba9d03cb7b6849586029",
    },
}
# Exact counts are pinned for v1, whose runs are already recorded; v2 is
# checked for internal consistency against its own READY.json instead.
V1_PINNED = {
    "centered_crop_quotas": {"van": 4065, "truck": 2217, "bus": 1108},
    "base_train_grid": {"images": 36565, "positive_images": 29559, "negative_images": 7006},
    "train_tiles": {"images": 42861, "centered_images": 7390, "negative_images": 5912},
    "validation_tiles": {"images": 7640, "negative_images": 725, "centered_images": 0},
}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    root = args.prepared.resolve()
    ready = load(root / "READY.json")

    assert ready["name"] in EXPECTED_HASHES, ready["name"]
    assert ready["classes"] == ["car", "van", "truck", "bus"]
    full_train = ready["name"] == "rfdetr-full-train-v1-ab"
    assert ready["train_images"] == (6471 if full_train else 5176)
    assert ready["validation_images"] == 1295
    assert ready.get("validation_overlap_images", 0) == (1295 if full_train else 0)
    assert ready["source_hashes"] == EXPECTED_HASHES[ready["name"]]
    if ready["name"] == "rfdetr-scene-holdout-v1-ab":
        assert ready["centered_crop_quotas"] == V1_PINNED["centered_crop_quotas"]
        assert ready["base_train_grid"] == V1_PINNED["base_train_grid"]
        for key in ("train_tiles", "validation_tiles"):
            for field, value in V1_PINNED[key].items():
                assert ready[key][field] == value, (key, field)
    quotas = ready["centered_crop_quotas"]
    assert ready["train_tiles"]["centered_images"] == sum(quotas.values())
    assert ready["validation_tiles"]["centered_images"] == 0

    train_original = load(root / "coco" / "train" / "_annotations.coco.json")
    valid_original = load(root / "coco" / "valid" / "_annotations.coco.json")
    train_ids = {str(image["original_image_id"]) for image in train_original["images"]}
    valid_ids = {str(image["original_image_id"]) for image in valid_original["images"]}
    assert len(train_ids) == (6471 if full_train else 5176) and len(valid_ids) == 1295
    if full_train:
        assert valid_ids <= train_ids
    else:
        assert not train_ids & valid_ids

    for split, key in (("train", "train_tiles"), ("valid", "validation_tiles")):
        expected_images = ready[key]["images"]
        split_dir = root / "rfdetr_tiles" / split
        payload = load(split_dir / "_annotations.coco.json")
        assert len(payload["images"]) == expected_images
        assert len({image["file_name"] for image in payload["images"]}) == expected_images
        assert all((split_dir / image["file_name"]).exists() for image in payload["images"])
        assert all(float(annotation["area"]) > 0 for annotation in payload["annotations"])
        tile_ids = {str(image["original_image_id"]) for image in payload["images"]}
        assert tile_ids <= (train_ids if split == "train" else valid_ids)
        counts = Counter(int(annotation["category_id"]) for annotation in payload["annotations"])
        expected_counts = ready[key]["annotation_class_counts"]
        assert [counts[index] for index in range(4)] == [
            expected_counts[name] for name in ("car", "van", "truck", "bus")
        ]

    train_tiles = load(root / "rfdetr_tiles" / "train" / "_annotations.coco.json")["images"]
    centered = [image for image in train_tiles if image["crop_kind"] == "centered"]
    assert Counter(image["focus_class"] for image in centered) == Counter(quotas)
    assert max(Counter(image["original_image_id"] for image in centered).values()) <= 4
    print(json.dumps(ready, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
