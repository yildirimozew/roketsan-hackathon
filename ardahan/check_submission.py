"""Validate a submission against data/sample_submission.csv before it goes anywhere.

Checks: same columns, same row count, same image_ids in the same order, no duplicates, no empty cells,
every PredictionString is "none" or groups of "label conf x y w h" with a known label,
0 <= conf <= 1, w and h > 0, finite numbers.

Usage: python ardahan/check_submission.py SUBMISSION.csv
"""
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLASSES = {"car", "van", "truck", "bus"}


def check(path) -> list[str]:
    sample = pd.read_csv(ROOT / "data/sample_submission.csv", dtype=str, keep_default_na=False)
    sub = pd.read_csv(path, dtype=str, keep_default_na=False)
    errs = []
    if list(sub.columns) != list(sample.columns):
        errs.append(f"columns {list(sub.columns)} != {list(sample.columns)}")
        return errs
    if len(sub) != len(sample):
        errs.append(f"{len(sub)} rows, sample has {len(sample)}")
    if sub.image_id.duplicated().any():
        errs.append(f"{sub.image_id.duplicated().sum()} duplicated image_ids")
    if set(sub.image_id) != set(sample.image_id):
        errs.append(f"image_ids differ: {len(set(sample.image_id) - set(sub.image_id))} missing, "
                    f"{len(set(sub.image_id) - set(sample.image_id))} extra")
    elif list(sub.image_id) != list(sample.image_id):
        errs.append("image_ids in a different order than the sample (allowed? keep the sample order to be safe)")
    bad = []
    for iid, s in zip(sub.image_id, sub.PredictionString):
        s = s.strip()
        if s == "":
            bad.append(f"{iid}: empty cell (write none)")
            continue
        if s == "none":
            continue
        tok = s.split()
        if len(tok) % 6:
            bad.append(f"{iid}: {len(tok)} tokens, not groups of 6")
            continue
        for k in range(0, len(tok), 6):
            lab, *nums = tok[k:k + 6]
            try:
                conf, x, y, w, h = map(float, nums)
            except ValueError:
                bad.append(f"{iid}: non-numeric in {tok[k:k + 6]}")
                break
            if lab not in CLASSES:
                bad.append(f"{iid}: unknown label {lab!r}")
                break
            if not all(map(math.isfinite, (conf, x, y, w, h))) or not 0 <= conf <= 1 or w <= 0 or h <= 0:
                bad.append(f"{iid}: bad values {tok[k:k + 6]}")
                break
    errs += bad[:10] + ([f"... {len(bad) - 10} more"] if len(bad) > 10 else [])
    return errs


def main():
    path = sys.argv[1]
    errs = check(path)
    sub = pd.read_csv(path, dtype=str, keep_default_na=False)
    n_none = (sub.PredictionString.str.strip() == "none").sum()
    n_boxes = sub.PredictionString.str.split().str.len().sum() // 6 if len(sub) else 0
    print(f"{len(sub)} rows, {n_none} 'none', ~{n_boxes} boxes, {Path(path).stat().st_size / 1e6:.1f} MB")
    print("OK" if not errs else "FAILED:\n  " + "\n  ".join(errs))
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
