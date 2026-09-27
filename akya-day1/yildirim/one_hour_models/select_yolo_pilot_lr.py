#!/usr/bin/env python3
"""Choose pilot 3's learning rate from the matched pilot 1/2 evaluations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def score(path: Path) -> float:
    return float(json.loads(path.read_text())["best"]["weighted_competition"]["map50"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot1", type=Path, required=True)
    parser.add_argument("--pilot2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-gain", type=float, default=0.005)
    args = parser.parse_args()
    pilot1, pilot2 = score(args.pilot1), score(args.pilot2)
    choose_lower = pilot2 >= pilot1 + args.minimum_gain
    result = {
        "pilot1_lr0": 0.001,
        "pilot1_weighted_map50": pilot1,
        "pilot2_lr0": 0.0005,
        "pilot2_weighted_map50": pilot2,
        "minimum_gain": args.minimum_gain,
        "selected_pilot": 2 if choose_lower else 1,
        "selected_lr0": 0.0005 if choose_lower else 0.001,
        "reason": "lower LR cleared minimum gain" if choose_lower else "control retained because lower LR did not clear minimum gain",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
