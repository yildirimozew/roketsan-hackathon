"""Detection confusion matrix: are errors misclassifications or missed boxes?

At a confidence threshold, predictions are matched to ground truth class-agnostically (highest confidence
first, IoU >= 0.5, each box used once). Then:
  rows = ground-truth class, columns = predicted class of the matched box, or "missed" (no box at IoU >= 0.5)
  last row = unmatched predictions (false positives on background or duplicates), by predicted class;
             predictions under 200 px^2 that match nothing are ignored, as in the competition.
The threshold is reported at 0.25 (Ultralytics' default operating point) and at the one that maximises
the micro-F1 of correctly classified matches.

Usage: python ardahan/confusion.py PREDS.csv --images splits/folds/fold_1_val.txt
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["car", "van", "truck", "bus"]


def iou(a, b):
    """a: (n,4) xywh, b: (m,4) xywh -> (n,m)"""
    ax2, ay2, bx2, by2 = a[:, 0] + a[:, 2], a[:, 1] + a[:, 3], b[:, 0] + b[:, 2], b[:, 1] + b[:, 3]
    iw = np.clip(np.minimum(ax2[:, None], bx2[None]) - np.maximum(a[:, 0][:, None], b[:, 0][None]), 0, None)
    ih = np.clip(np.minimum(ay2[:, None], by2[None]) - np.maximum(a[:, 1][:, None], b[:, 1][None]), 0, None)
    inter = iw * ih
    return inter / (a[:, 2:].prod(1)[:, None] + b[:, 2:].prod(1)[None] - inter + 1e-9)


def match(gt, preds, image_ids, thr):
    cols = CLASSES + ["missed"]
    M = pd.DataFrame(0, index=CLASSES + ["unmatched pred"], columns=cols)
    g_by, p_by = dict(tuple(gt.groupby("image_id"))), dict(tuple(preds[preds.conf >= thr].groupby("image_id")))
    for iid in image_ids:
        g, p = g_by.get(iid), p_by.get(iid)
        gl = [] if g is None else list(g.label)
        if p is None:
            for c in gl:
                M.loc[c, "missed"] += 1
            continue
        p = p.sort_values("conf", ascending=False)
        pb, pl = p[["x", "y", "w", "h"]].to_numpy(float), list(p.label)
        used = np.zeros(len(gl), bool)
        if gl:
            ious = iou(pb, g[["x", "y", "w", "h"]].to_numpy(float))
        for k in range(len(pb)):
            j = -1
            if gl:
                cand = np.where(~used & (ious[k] >= 0.5))[0]
                if len(cand):
                    j = cand[np.argmax(ious[k, cand])]
            if j >= 0:
                used[j] = True
                M.loc[gl[j], pl[k]] += 1
            elif pb[k, 2] * pb[k, 3] >= 200:
                M.loc["unmatched pred", pl[k]] += 1
        for j in np.where(~used)[0]:
            M.loc[gl[j], "missed"] += 1
    return M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("preds")
    ap.add_argument("--images", required=True)
    a = ap.parse_args()
    ids = (ROOT / a.images).read_text().split() if not Path(a.images).is_absolute() else Path(a.images).read_text().split()
    gt = pd.read_csv(ROOT / "data/train/annotations.csv")
    gt = gt[gt.image_id.isin(ids)]
    preds = pd.read_csv(a.preds)
    preds = preds[preds.image_id.isin(ids)]

    best = None
    for thr in np.arange(0.05, 0.9, 0.05):
        M = match(gt, preds, ids, thr)
        tp = sum(M.loc[c, c] for c in CLASSES)
        f1 = 2 * tp / (2 * tp + (M.loc[CLASSES, "missed"].sum() + M.loc[CLASSES, CLASSES].to_numpy().sum() - tp)
                       + M.loc["unmatched pred"].sum() + (M.loc[CLASSES, CLASSES].to_numpy().sum() - tp))
        if best is None or f1 > best[0]:
            best = (f1, thr, M)
    for label, thr, M in [("conf >= 0.25", 0.25, match(gt, preds, ids, 0.25)),
                          (f"conf >= {best[1]:.2f} (best micro-F1 {best[0]:.3f})", best[1], best[2])]:
        print(f"\n## {label}: counts (rows: ground truth, columns: prediction)")
        print(M.to_string())
        R = M.loc[CLASSES].div(M.loc[CLASSES].sum(1), axis=0) * 100
        print("row %: of each ground-truth class, share predicted as ... / missed")
        print(R.round(1).to_string())


if __name__ == "__main__":
    main()
