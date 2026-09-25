#!/usr/bin/env python3
"""Validate the deterministic sliced YOLO pilot dataset before using a GPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prepare_rfdetr_ab import sha256_file


def manifest_paths(root: Path, name: str) -> list[Path]:
    return [(root / line).resolve() for line in (root / name).read_text().splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    root = args.prepared.resolve()
    repo = args.repo.resolve()
    ready = json.loads((root / "READY.json").read_text())

    assert ready["name"] == "yolo26-s-p2-scene-holdout-v2-sliced-pilots"
    assert ready["classes"] == ["car", "van", "truck", "bus"]
    assert ready["train_images"] == 5176
    assert ready["validation_images"] == 1295
    assert ready["parameters"]["tile_size"] == 704
    assert ready["parameters"]["tile_overlap"] == 0.25
    assert ready["parameters"]["negative_ratio"] == 0.20
    assert ready["parameters"]["seed"] == 42
    assert set(ready["ratios"]) == {"ratio25", "ratio40"}

    sources = {
        "annotations.csv": repo / "data/train/annotations.csv",
        "train.txt": repo / "splits/scene_holdout_v2/train.txt",
        "val.txt": repo / "splits/scene_holdout_v2/val.txt",
        "val_strata.csv": repo / "splits/scene_holdout_v2/val_strata.csv",
    }
    for name, path in sources.items():
        assert sha256_file(path) == ready["source_hashes"][name], name

    validation = manifest_paths(root, "val.txt")
    assert len(validation) == ready["validation"]["images"] == 1295
    assert all(path.exists() for path in validation)

    for name, expected_ratio in (("ratio25", 0.25), ("ratio40", 0.40)):
        details = ready["ratios"][name]
        assert details["centered_ratio"] == expected_ratio
        assert details["max_centered_per_image"] == (4 if name == "ratio25" else 6)
        manifest = root / f"train_{name}.txt"
        assert sha256_file(manifest) == details["train_manifest_sha256"]
        images = manifest_paths(root, manifest.name)
        assert len(images) == details["total_train_images"]
        assert len(images) == ready["selected_grid"]["images"] + details["centered_tiles"]["images"]
        assert all(path.exists() for path in images)
        for image_path in images:
            label_path = Path(str(image_path).replace("/images/", "/labels/")).with_suffix(".txt")
            assert label_path.exists(), label_path
        assert (root / details["dataset_yaml"]).exists()

    print(json.dumps({
        "prepared": str(root),
        "grid_images": ready["selected_grid"]["images"],
        "ratio25_images": ready["ratios"]["ratio25"]["total_train_images"],
        "ratio40_images": ready["ratios"]["ratio40"]["total_train_images"],
        "status": "ok",
    }, indent=2))


if __name__ == "__main__":
    main()
