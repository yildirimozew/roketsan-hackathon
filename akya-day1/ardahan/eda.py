"""Dataset stats: image sizes, box areas per class (near the 200 px^2 floor), boxes per image.

Usage: python ardahan/eda.py  (run from the repo root)
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CLASSES = ["car", "van", "truck", "bus"]


def image_sizes(folder: Path) -> pd.DataFrame:
    paths = sorted(folder.glob("*.jpg"))

    def size(p):
        with Image.open(p) as im:  # header only, no decode
            return p.stem, im.width, im.height

    with ThreadPoolExecutor(16) as ex:
        rows = list(ex.map(size, paths))
    return pd.DataFrame(rows, columns=["image_id", "width", "height"])


def main():
    ann = pd.read_csv(DATA / "train/annotations.csv")
    tr = image_sizes(DATA / "train/images")
    te = image_sizes(DATA / "test/images")
    tr.to_csv(ROOT / "ardahan/image_sizes_train.csv", index=False)
    te.to_csv(ROOT / "ardahan/image_sizes_test.csv", index=False)

    print("## Image sizes (WxH: count)")
    for name, df in [("train", tr), ("test", te)]:
        vc = (df.width.astype(str) + "x" + df.height.astype(str)).value_counts()
        print(f"{name}: {len(df)} images")
        print(vc.head(10).to_string())

    ann["area"] = ann.w * ann.h
    ann = ann.merge(tr, on="image_id", how="left")
    print(f"\nboxes with no image: {ann.width.isna().sum()}")
    oob = (ann.x < 0) | (ann.y < 0) | (ann.x + ann.w > ann.width) | (ann.y + ann.h > ann.height)
    print(f"boxes out of image bounds: {oob.sum()}   degenerate (w or h <= 0): {((ann.w <= 0) | (ann.h <= 0)).sum()}")
    print(f"boxes with area < 200: {(ann.area < 200).sum()}")

    print("\n## Box area per class (px^2)")
    q = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    tab = ann.groupby("label").area.quantile(q).unstack().round(0)
    tab.insert(0, "n", ann.label.value_counts())
    print(tab.loc[CLASSES].to_string())

    print("\n## Near the floor: share of boxes by area bin")
    bins = [200, 300, 400, 600, 1000, 2000, 5000, np.inf]
    labels = ["200-300", "300-400", "400-600", "600-1k", "1k-2k", "2k-5k", "5k+"]
    ann["bin"] = pd.cut(ann.area, bins, right=False, labels=labels)
    ct = pd.crosstab(ann.label, ann.bin)
    print(ct.loc[CLASSES].to_string())
    print((ct.div(ct.sum(1), axis=0) * 100).round(1).loc[CLASSES].to_string())

    print("\n## Short side of the box (px) per class")
    ann["short"] = ann[["w", "h"]].min(1)
    print(ann.groupby("label").short.quantile([0.05, 0.25, 0.5]).unstack().loc[CLASSES].to_string())

    print("\n## Relative size: box sqrt(area) / image long side, and at imgsz 1280 / 640")
    ann["rel"] = np.sqrt(ann.area) / ann[["width", "height"]].max(1)
    for s in [640, 1280]:
        px = ann.rel * s
        print(f"imgsz {s}: median box side {px.median():.1f} px, "
              f"share < 8 px {100 * (px < 8).mean():.1f}%, < 16 px {100 * (px < 16).mean():.1f}%")

    print("\n## Boxes per image")
    per = ann.groupby("image_id").size().reindex(tr.image_id, fill_value=0)
    print(per.describe(percentiles=[0.5, 0.9, 0.99]).round(1).to_string())
    print(f"images with 0 boxes: {(per == 0).sum()}, > 100: {(per > 100).sum()}, > 300: {(per > 300).sum()}, max {per.max()}")
    per_cls = ann.groupby(["image_id", "label"]).size().unstack(fill_value=0)
    print("max per class in one image:", per_cls.max().to_dict())


if __name__ == "__main__":
    main()
