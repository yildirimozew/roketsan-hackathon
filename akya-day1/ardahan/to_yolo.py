"""Convert data/train/annotations.csv to a YOLO dataset that uses the committed fold manifests.

Writes ardahan/outputs/yolo_ds/ (gitignored):
  images/train/*.jpg, images/test/*.jpg   hard links to data/, no copies
  labels/train/*.txt                      "cls cx cy w h", normalised; empty file for background images
  fold_{k}_train.txt, fold_{k}_val.txt    "./images/train/<id>.jpg", straight from splits/folds/
  classes.json                            class order, shared with the evaluator and inference

Class order is fixed: car=0, van=1, truck=2, bus=3.

Usage: python ardahan/to_yolo.py   (from the repo root)
"""
import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "ardahan/outputs/yolo_ds"
CLASSES = ["car", "van", "truck", "bus"]


def link_images(src: Path, dst: Path) -> list[str]:
    dst.mkdir(parents=True, exist_ok=True)
    ids = []
    for p in sorted(src.glob("*.jpg")):
        target = dst / p.name
        if not target.exists():
            os.link(p, target)
        ids.append(p.stem)
    return ids


def main():
    sizes = pd.read_csv(ROOT / "ardahan/image_sizes_train.csv").set_index("image_id")
    ann = pd.read_csv(DATA / "train/annotations.csv")
    train_ids = link_images(DATA / "train/images", OUT / "images/train")
    link_images(DATA / "test/images", OUT / "images/test")

    ann = ann.join(sizes, on="image_id")
    ann["cls"] = ann.label.map({c: i for i, c in enumerate(CLASSES)})
    assert ann.cls.notna().all(), "unknown label"
    ann["cx"] = (ann.x + ann.w / 2) / ann.width
    ann["cy"] = (ann.y + ann.h / 2) / ann.height
    ann["nw"] = ann.w / ann.width
    ann["nh"] = ann.h / ann.height

    lab = OUT / "labels/train"
    lab.mkdir(parents=True, exist_ok=True)
    groups = dict(tuple(ann.groupby("image_id")))
    for iid in train_ids:
        g = groups.get(iid)
        lines = [] if g is None else [
            f"{int(r.cls)} {r.cx:.6f} {r.cy:.6f} {r.nw:.6f} {r.nh:.6f}" for r in g.itertuples()
        ]
        (lab / f"{iid}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))

    all_ids = set(train_ids)
    for k in range(1, 6):
        tr = (ROOT / f"splits/folds/fold_{k}_train.txt").read_text().split()
        va = (ROOT / f"splits/folds/fold_{k}_val.txt").read_text().split()
        assert not set(tr) & set(va), f"fold {k}: train/val overlap"
        assert set(tr) | set(va) == all_ids, f"fold {k}: manifests don't cover the images"
        for name, ids in [("train", tr), ("val", va)]:
            (OUT / f"fold_{k}_{name}.txt").write_text("".join(f"./images/train/{i}.jpg\n" for i in ids))

    (OUT / "classes.json").write_text(json.dumps(CLASSES))
    print(f"{len(train_ids)} train images, {len(ann)} boxes, "
          f"{len(train_ids) - len(groups)} background, 5 folds -> {OUT}")


if __name__ == "__main__":
    main()
