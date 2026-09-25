#!/usr/bin/env python3
"""Fail-fast integrity checks for the RF-DETR scene-holdout A/B dataset."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


EXPECTED_HASHES = {
    "annotations.csv": "c946f29a627438bc4567544cc654234df2eab6a8e342a9ee4d9a6fd997e857ce",
    "train.txt": "f4cc66110bc17ba00bbbadb21de55c7f906d5bc505c1cfcbb49833cb2b148678",
    "val.txt": "c0ddf4ef726abebd8687a02ea036b0ec79947d801070ba9d03cb7b6849586029",
}
EXPECTED_QUOTAS = {"van": 4065, "truck": 2217, "bus": 1108}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    root = args.prepared.resolve()
    ready = load(root / "READY.json")

    assert ready["name"] == "rfdetr-scene-holdout-v1-ab"
    assert ready["classes"] == ["car", "van", "truck", "bus"]
    assert ready["train_images"] == 5176
    assert ready["validation_images"] == 1295
    assert ready["source_hashes"] == EXPECTED_HASHES
    assert ready["centered_crop_quotas"] == EXPECTED_QUOTAS
    assert ready["base_train_grid"] == {
        "images": 36565,
        "positive_images": 29559,
        "negative_images": 7006,
    }
    assert ready["train_tiles"]["images"] == 42861
    assert ready["train_tiles"]["centered_images"] == 7390
    assert ready["train_tiles"]["negative_images"] == 5912
    assert ready["validation_tiles"]["images"] == 7640
    assert ready["validation_tiles"]["negative_images"] == 725
    assert ready["validation_tiles"]["centered_images"] == 0

    train_original = load(root / "coco" / "train" / "_annotations.coco.json")
    valid_original = load(root / "coco" / "valid" / "_annotations.coco.json")
    train_ids = {str(image["original_image_id"]) for image in train_original["images"]}
    valid_ids = {str(image["original_image_id"]) for image in valid_original["images"]}
    assert len(train_ids) == 5176 and len(valid_ids) == 1295
    assert not train_ids & valid_ids

    for split, expected_images in (("train", 42861), ("valid", 7640)):
        split_dir = root / "rfdetr_tiles" / split
        payload = load(split_dir / "_annotations.coco.json")
        assert len(payload["images"]) == expected_images
        assert len({image["file_name"] for image in payload["images"]}) == expected_images
        assert all((split_dir / image["file_name"]).exists() for image in payload["images"])
        assert all(float(annotation["area"]) > 0 for annotation in payload["annotations"])
        counts = Counter(int(annotation["category_id"]) for annotation in payload["annotations"])
        expected_counts = ready[f"{'train' if split == 'train' else 'validation'}_tiles"][
            "annotation_class_counts"
        ]
        assert [counts[index] for index in range(4)] == [
            expected_counts[name] for name in ("car", "van", "truck", "bus")
        ]

    train_tiles = load(root / "rfdetr_tiles" / "train" / "_annotations.coco.json")["images"]
    centered = [image for image in train_tiles if image["crop_kind"] == "centered"]
    assert Counter(image["focus_class"] for image in centered) == Counter(EXPECTED_QUOTAS)
    assert max(Counter(image["original_image_id"] for image in centered).values()) <= 4
    print(json.dumps(ready, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
