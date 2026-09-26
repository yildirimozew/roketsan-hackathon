"""Synthetic val predictions from GT, for testing post-processing only (NOT a model)."""
import argparse
import numpy as np, pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--images", default="splits/scene_holdout_v2/val.txt")
ap.add_argument("--annotations", default="data/train/annotations.csv")
ap.add_argument("--out", default="mustafa/preds/fake_val.csv")
ap.add_argument("--seed", type=int, default=42)
a = ap.parse_args()
rng = np.random.default_rng(a.seed)
ids = open(a.images).read().split()
gt = pd.read_csv(a.annotations)
gt = gt[gt.image_id.isin(set(ids))].reset_index(drop=True)
gt = gt[rng.random(len(gt)) >= 0.10].reset_index(drop=True)          # drop 10%
n = len(gt)
p = gt.copy()
p["x"] += rng.uniform(-.05, .05, n) * p.w; p["y"] += rng.uniform(-.05, .05, n) * p.h
p["w"] *= 1 + rng.uniform(-.05, .05, n); p["h"] *= 1 + rng.uniform(-.05, .05, n)
p["conf"] = rng.uniform(.5, 1.0, n)
flip = {"car": ("van", .15), "van": ("car", .25), "truck": ("bus", .15)}
u = rng.random(n); orig = p.label.copy()
for src, (dst, q) in flip.items():
    m = (orig == src) & (u < q)
    p.loc[m, "label"] = dst; p.loc[m, "conf"] = rng.uniform(.4, .8, m.sum())
size = gt.groupby("image_id")[["x", "y", "w", "h"]].agg({"x": "max", "y": "max", "w": "max", "h": "max"})
fp = []
for iid in ids:                                                       # 3 false boxes / image
    W, H = (size.loc[iid, "x"] + size.loc[iid, "w"], size.loc[iid, "y"] + size.loc[iid, "h"]) if iid in size.index else (1280, 720)
    for _ in range(3):
        w, h = rng.uniform(20, 200), rng.uniform(20, 150)
        fp.append((iid, rng.choice(["car", "van", "truck", "bus"]), rng.uniform(.05, .4),
                   rng.uniform(0, max(W - w, 1)), rng.uniform(0, max(H - h, 1)), w, h))
p = pd.concat([p[["image_id", "label", "conf", "x", "y", "w", "h"]],
               pd.DataFrame(fp, columns=["image_id", "label", "conf", "x", "y", "w", "h"])], ignore_index=True)
p.to_csv(a.out, index=False)
print(f"{a.out}: {len(p)} boxes, {len(ids)} images")
