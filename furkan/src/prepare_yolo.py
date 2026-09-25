"""Convert data/train/annotations.csv to a YOLO dataset that uses splits/scene_holdout_v2.

Follows ardahan/to_yolo.py's conventions. Writes furkan/outputs/yolo_v2/ (gitignored):
  images/train/*.jpg, images/test/*.jpg   hard links to data/ (copied, with a warning, if linking fails)
  labels/train/*.txt                      "cls cx cy w h", normalised to [0, 1]; empty file for background images
  train.txt, val.txt, val_1400x788.txt, val_dark.txt, val_1400x788_dark.txt, test.txt
                                          "./images/<split>/<id>.jpg"
  data_sh_v2.yaml                         path / train / val / names only (no hyperparameters)
  classes.json                            class order, shared with the evaluator and inference
  _check/*.jpg                            3 random train images with their labels drawn back from the .txt files

Class order is fixed: car=0, van=1, truck=2, bus=3.

Usage: python furkan/src/prepare_yolo.py   (from the repo root, after make_scene_holdout_v2.py)
"""
import json
import os
import random
import shutil
import warnings
from pathlib import Path

import cv2
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SPLIT = ROOT / "splits/scene_holdout_v2"
OUT = ROOT / "furkan/outputs/yolo_v2"
CLASSES = ["car", "van", "truck", "bus"]
SEED = 42
COLORS = [(0, 255, 0), (255, 200, 0), (0, 128, 255), (0, 0, 255)]


def link_images(src: Path, dst: Path) -> list[str]:
    dst.mkdir(parents=True, exist_ok=True)
    ids, copied = [], 0
    for p in sorted(src.glob("*.jpg")):
        target = dst / p.name
        if not target.exists():
            try:
                os.link(p, target)
            except OSError:
                shutil.copy2(p, target)
                copied += 1
        ids.append(p.stem)
    if copied:
        warnings.warn(f"hard link failed for {copied} images in {dst}; copied them instead")
    return ids


def write_list(name, folder, ids):
    (OUT / name).write_text("".join(f"./images/{folder}/{i}.jpg\n" for i in ids), newline="\n")


def draw_check(ids):
    check = OUT / "_check"
    check.mkdir(exist_ok=True)
    for iid in random.Random(SEED).sample(ids, 3):
        im = cv2.imread(str(OUT / f"images/train/{iid}.jpg"))
        h, w = im.shape[:2]
        for line in (OUT / f"labels/train/{iid}.txt").read_text().splitlines():
            c, cx, cy, bw, bh = line.split()
            c, cx, cy, bw, bh = int(c), float(cx) * w, float(cy) * h, float(bw) * w, float(bh) * h
            p1, p2 = (round(cx - bw / 2), round(cy - bh / 2)), (round(cx + bw / 2), round(cy + bh / 2))
            cv2.rectangle(im, p1, p2, COLORS[c], 2)
            cv2.putText(im, CLASSES[c], (p1[0], max(p1[1] - 3, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLORS[c], 1)
        cv2.imwrite(str(check / f"{iid}.jpg"), im)
    return check


def main():
    raw = pd.read_csv(DATA / "train/annotations.csv")
    ann = raw.drop_duplicates().copy()
    assert len(raw) - len(ann) == 1, "expected exactly 1 exact duplicate annotation row"

    train_ids = link_images(DATA / "train/images", OUT / "images/train")
    test_ids = link_images(DATA / "test/images", OUT / "images/test")
    sizes = {}
    for iid in train_ids:
        with Image.open(OUT / f"images/train/{iid}.jpg") as im:
            sizes[iid] = im.size
    sizes = pd.DataFrame.from_dict(sizes, orient="index", columns=["width", "height"])

    ann = ann.join(sizes, on="image_id")
    ann["cls"] = ann.label.map({c: i for i, c in enumerate(CLASSES)})
    assert ann.cls.notna().all(), "unknown label"
    # clip box corners to the image, then normalise, so every value lies in [0, 1]
    x1, y1 = ann.x.clip(0, ann.width), ann.y.clip(0, ann.height)
    x2, y2 = (ann.x + ann.w).clip(0, ann.width), (ann.y + ann.h).clip(0, ann.height)
    clipped = int(((x1 != ann.x) | (y1 != ann.y) | (x2 != ann.x + ann.w) | (y2 != ann.y + ann.h)).sum())
    ann["cx"] = (x1 + x2) / 2 / ann.width
    ann["cy"] = (y1 + y2) / 2 / ann.height
    ann["nw"] = (x2 - x1) / ann.width
    ann["nh"] = (y2 - y1) / ann.height
    degenerate = int(((ann.nw <= 0) | (ann.nh <= 0)).sum())
    if clipped:
        warnings.warn(f"{clipped} boxes extended past the image border and were clipped; {degenerate} are now zero-sized")

    lab = OUT / "labels/train"
    lab.mkdir(parents=True, exist_ok=True)
    groups = dict(tuple(ann.groupby("image_id")))
    for iid in train_ids:
        g = groups.get(iid)
        lines = [] if g is None else [
            f"{int(r.cls)} {r.cx:.6f} {r.cy:.6f} {r.nw:.6f} {r.nh:.6f}" for r in g.itertuples()
        ]
        (lab / f"{iid}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), newline="\n")
    n_background = len(train_ids) - len(groups)
    assert len(ann) == 165348 and n_background == 290, (len(ann), n_background)

    tr = (SPLIT / "train.txt").read_text().split()
    va = (SPLIT / "val.txt").read_text().split()
    assert not set(tr) & set(va), "train/val overlap"
    assert set(tr) | set(va) == set(train_ids), "manifests don't cover the images"
    strata = pd.read_csv(SPLIT / "val_strata.csv").set_index("image_id").loc[va]
    lists = {
        "train.txt": ("train", tr),
        "val.txt": ("train", va),
        "val_1400x788.txt": ("train", [i for i in va if strata.is_1400x788[i]]),
        "val_dark.txt": ("train", [i for i in va if strata.is_dark[i]]),
        "val_1400x788_dark.txt": ("train", [i for i in va if strata.is_1400x788_dark[i]]),
        "test.txt": ("test", test_ids),
    }
    for name, (folder, ids) in lists.items():
        write_list(name, folder, ids)

    yaml = (f"path: {OUT.as_posix()}\ntrain: train.txt\nval: val.txt\nnames:\n"
            + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)))
    (OUT / "data_sh_v2.yaml").write_text(yaml, newline="\n")
    (OUT / "classes.json").write_text(json.dumps(CLASSES))

    check = draw_check(train_ids)
    try:
        from ultralytics.data.utils import check_det_dataset
    except ImportError:
        print("ultralytics not installed: skipped check_det_dataset")
    else:
        info = check_det_dataset(str(OUT / "data_sh_v2.yaml"))
        print(f"check_det_dataset ok: nc={info['nc']}, names={info['names']}")

    print(f"{len(train_ids)} train images, {len(test_ids)} test images, {len(ann)} boxes, "
          f"{n_background} background, {clipped} clipped / {degenerate} zero-sized boxes")
    print("lists: " + ", ".join(f"{n} {len(ids)}" for n, (_, ids) in lists.items()))
    print(f"-> {OUT}; label check images in {check}")


if __name__ == "__main__":
    main()
