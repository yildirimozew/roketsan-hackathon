#!/usr/bin/env python3
"""Evaluate the newest usable RF-DETR checkpoint on the tiled validation set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rfdetr import RFDETRLarge


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidates = sorted(args.output.glob("checkpoint_best*.pth"))
    candidates += sorted(args.output.glob("checkpoint_epoch=*.ckpt"), reverse=True)
    candidates += sorted(args.output.glob("checkpoint_*.ckpt"), reverse=True)
    candidates += sorted(args.output.glob("*.pth"), reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No RF-DETR checkpoint found in {args.output}")
    checkpoint = candidates[0]
    model = RFDETRLarge(pretrain_weights=str(checkpoint), resolution=704)
    metrics = model.evaluate(dataset_dir=str(args.data.resolve()), split="val")
    serializable = {
        "checkpoint": str(checkpoint),
        "metrics": str(metrics),
        "evaluation_unit": "704px validation tiles",
    }
    (args.output / "metrics.json").write_text(json.dumps(serializable, indent=2) + "\n")
    print(json.dumps(serializable, indent=2))


if __name__ == "__main__":
    main()
