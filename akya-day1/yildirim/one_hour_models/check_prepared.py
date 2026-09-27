#!/usr/bin/env python3
"""Fast integrity checks run before any GPU allocation starts training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    root = args.prepared
    marker = json.loads((root / "READY.json").read_text())
    assert marker["train_images"] == 5176
    assert marker["validation_images"] == 1295
    assert marker["classes"] == ["car", "van", "truck", "bus"]
    assert (root / "yolo" / "dataset.yaml").exists()
    for dataset in ("coco", "rfdetr_tiles"):
        for split in ("train", "valid"):
            path = root / dataset / split / "_annotations.coco.json"
            payload = json.loads(path.read_text())
            assert len(payload["categories"]) == 4
            assert payload["images"]
            assert all(annotation["area"] >= 0 for annotation in payload["annotations"])
    print(json.dumps(marker, indent=2))


if __name__ == "__main__":
    main()
