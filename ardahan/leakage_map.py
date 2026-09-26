"""How much does near-duplicate leakage inflate fold-1 mAP? Two measurements.

A. What was asked: the zero-shot COCO model (never trained on our data) scored on committed fold-1 val
   and on grouped fold-1 val (ardahan/splits/grouped_dinov2). Caveat: a model that never saw the training
   split cannot benefit from leakage, so this difference measures how hard the two validation sets are,
   not inflation.
B. The inflation itself: nano (trained on committed fold-1 train) scored on the fold-1 val images that have
   a near-copy in fold-1 train vs those that don't, minus the same gap for the zero-shot model on the same
   images (difference-in-differences: the zero-shot gap absorbs how hard the two subsets are).

Confidence intervals: bootstrap over images (stratified by subset). pycocotools matching runs once per
model; AP is recomputed from the per-image matches, COCO-style 101-point interpolation. Checked against
ardahan/evaluate.py on the full set before use.

Usage: python ardahan/leakage_map.py   (from the repo root; needs the zero-shot and nano predictions)
"""
import contextlib
import io
from pathlib import Path

import numpy as np
import pandas as pd
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

from evaluate import CLASSES, MAX_DETS, MIN_AREA, evaluate

ROOT = Path(__file__).resolve().parents[1]
ZS = ROOT / "ardahan/outputs/coco_zeroshot"
NANO = ROOT / "ardahan/outputs/kaggle_yolo11n_fast/preds_val_fold1.csv"
R = np.linspace(0, 1, 101)


class PerImage:
    """pycocotools matching once; AP for any multiset of images from the stored per-image results."""

    def __init__(self, gt, preds, image_ids):
        self.ids = list(dict.fromkeys(image_ids))
        img = {iid: k + 1 for k, iid in enumerate(self.ids)}
        cat = {c: k + 1 for k, c in enumerate(CLASSES)}
        gt = gt[gt.image_id.isin(img)]
        preds = preds[preds.image_id.isin(img)]
        cg = COCO()
        cg.dataset = {"images": [{"id": i} for i in img.values()],
                      "categories": [{"id": i} for i in cat.values()],
                      "annotations": [{"id": k + 1, "image_id": img[r.image_id], "category_id": cat[r.label],
                                       "bbox": [r.x, r.y, r.w, r.h], "area": r.w * r.h, "iscrowd": 0}
                                      for k, r in enumerate(gt.itertuples())]}
        with contextlib.redirect_stdout(io.StringIO()):
            cg.createIndex()
            cd = cg.loadRes([{"image_id": img[r.image_id], "category_id": cat[r.label],
                              "bbox": [r.x, r.y, r.w, r.h], "score": r.conf} for r in preds.itertuples()])
            ev = COCOeval(cg, cd, "bbox")
            ev.params.imgIds = list(img.values())
            ev.params.iouThrs = np.array([0.5])
            ev.params.areaRng = [[MIN_AREA, 1e10]]
            ev.params.areaRngLbl = ["all"]
            ev.params.maxDets = [MAX_DETS]
            ev.evaluate()
            ev.accumulate()
        self.full = ev.eval["precision"][0, :, :, 0, 0]
        # per (class, image): scores, tp flags (non-ignored dets), number of non-ignored gt
        self.r = {c: {} for c in CLASSES}
        n_img = len(self.ids)
        for k, e in enumerate(ev.evalImgs):
            if e is None:
                continue
            c = CLASSES[e["category_id"] - 1]
            keep = ~np.asarray(e["dtIgnore"][0], bool)
            s = np.asarray(e["dtScores"])[keep]
            tp = (np.asarray(e["dtMatches"][0]) > 0)[keep]
            npos = int((~np.asarray(e["gtIgnore"], bool)).sum())
            self.r[c][self.ids[e["image_id"] - 1]] = (s, tp, npos)
        assert n_img

    def ap(self, image_ids, weights=None):
        """AP per class and their mean over the given images (a multiset). weights: optional {image_id: w};
        each image's ground truth, hits and false positives then count w times (importance weighting)."""
        out = {}
        for c in CLASSES:
            keep = [i for i in image_ids if i in self.r[c]]
            parts = [self.r[c][i] for i in keep]
            w = [1.0 if weights is None else float(weights[i]) for i in keep]
            npos = sum(p[2] * wi for p, wi in zip(parts, w))
            if npos == 0:
                out[c] = np.nan
                continue
            s = np.concatenate([p[0] for p in parts]) if parts else np.zeros(0)
            tp = np.concatenate([p[1] for p in parts]) if parts else np.zeros(0, bool)
            ww = np.concatenate([np.full(len(p[0]), wi) for p, wi in zip(parts, w)]) if parts else np.zeros(0)
            if len(s) == 0:  # ground truth but no detections (zero-shot van)
                out[c] = 0.0
                continue
            o = np.argsort(-s, kind="mergesort")
            tp, ww = tp[o], ww[o]
            ctp, cfp = np.cumsum(tp * ww), np.cumsum(~tp * ww)
            rec = ctp / npos
            prec = ctp / np.maximum(ctp + cfp, np.spacing(1))
            prec = np.maximum.accumulate(prec[::-1])[::-1]  # precision envelope
            idx = np.searchsorted(rec, R, side="left")
            q = np.where(idx < len(prec), prec[np.minimum(idx, len(prec) - 1)], 0)
            out[c] = float(q.mean())
        out["mAP"] = float(np.nanmean([out[c] for c in CLASSES]))
        return out


def boot(fn, groups, n=1000, seed=0):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        vals.append(fn([list(rng.choice(g, len(g))) for g in groups]))
    return np.percentile(vals, [2.5, 97.5])


def predict_zero_shot(image_ids):
    from ultralytics import YOLO

    from coco_zeroshot import WEIGHTS, predict
    return predict(YOLO(str(WEIGHTS)), [ROOT / f"data/train/images/{i}.jpg" for i in image_ids], 1280)


def main():
    gt = pd.read_csv(ROOT / "data/train/annotations.csv")
    f1 = (ROOT / "splits/folds/fold_1_val.txt").read_text().split()
    g1 = (ROOT / "ardahan/splits/grouped_dinov2/fold_1_val.txt").read_text().split()

    zs = pd.read_csv(ZS / "preds_val_fold1.csv")
    extra_path = ZS / "preds_val_grouped_fold1_extra.csv"
    missing = sorted(set(g1) - set(zs.image_id) - set(f1))
    if not extra_path.exists():
        print(f"zero-shot on {len(missing)} grouped fold-1 val images not predicted before ...", flush=True)
        predict_zero_shot(missing).to_csv(extra_path, index=False)
    zs = pd.concat([zs, pd.read_csv(extra_path)])
    print(f"overlap between committed fold-1 val and grouped fold-1 val: {len(set(f1) & set(g1))} images")

    # sanity: per-image AP reproduces evaluate.py
    zs_all = PerImage(gt, zs, list(dict.fromkeys(f1 + g1)))
    for name, ids in [("committed fold-1 val", f1), ("grouped fold-1 val", g1)]:
        ref = evaluate(gt, zs, ids)["mAP50"]
        mine = zs_all.ap(ids)["mAP"]
        assert abs(ref - mine) < 1e-6, (name, ref, mine)
    print("per-image AP matches evaluate.py on both sets\n")

    print("## A. zero-shot COCO yolo11m (no training on our data; van AP is 0 by construction)")
    a, b = zs_all.ap(f1), zs_all.ap(g1)
    for name, r in [("committed fold-1 val", a), ("grouped fold-1 val", b)]:
        print(f"  {name:22s} mAP {r['mAP']:.4f}   " + "  ".join(f"{c} {r[c]:.3f}" for c in CLASSES))
    lo, hi = boot(lambda g: zs_all.ap(g[0])["mAP"] - zs_all.ap(g[1])["mAP"], [f1, g1], n=500)
    print(f"  committed - grouped: {a['mAP'] - b['mAP']:+.4f}  (95% CI {lo:+.4f} .. {hi:+.4f})")

    print("\n## B. inflation: nano (trained on committed fold-1 train) vs zero-shot, fold-1 val split by near-copy")
    sims = pd.read_csv(ROOT / "ardahan/outputs/embeddings/fold1_val_max_sim.csv").set_index("image_id").max_sim
    nano = PerImage(gt, pd.read_csv(NANO), f1)
    zs_f1 = PerImage(gt, zs, f1)
    bins = {">= 0.90 (same scene)": sims[sims >= 0.90].index.tolist(),
            "0.85-0.90": sims[(sims >= 0.85) & (sims < 0.90)].index.tolist(),
            "< 0.85": sims[sims < 0.85].index.tolist()}
    print(f"  {'best match in fold-1 train':26s} {'images':>6s}   nano mAP   zero-shot mAP (car/truck/bus only)")
    zs3 = lambda r: np.nanmean([r[c] for c in ["car", "truck", "bus"]])  # noqa: E731
    for name, ids in bins.items():
        n, z = nano.ap(ids), zs_f1.ap(ids)
        print(f"  {name:26s} {len(ids):6d}   {n['mAP']:.4f}     {zs3(z):.4f}")
    near, far = bins[">= 0.90 (same scene)"], bins["< 0.85"]
    # nano over its 4 classes; the zero-shot control over the 3 classes it can predict, as a difficulty index
    did = lambda g: (nano.ap(g[0])["mAP"] - nano.ap(g[1])["mAP"]) - (zs3(zs_f1.ap(g[0])) - zs3(zs_f1.ap(g[1])))  # noqa: E731
    nano_gap = nano.ap(near)["mAP"] - nano.ap(far)["mAP"]
    zs_gap = zs3(zs_f1.ap(near)) - zs3(zs_f1.ap(far))
    lo, hi = boot(did, [near, far], n=500)
    print(f"\n  nano gap (near - far)       {nano_gap:+.4f}")
    print(f"  zero-shot gap (near - far)  {zs_gap:+.4f}   (how much easier the near-copy images are anyway)")
    print(f"  difference-in-differences   {nano_gap - zs_gap:+.4f}  (95% CI {lo:+.4f} .. {hi:+.4f})")
    share = len(near) / len(f1)
    print(f"  => estimated inflation of nano's full fold-1 mAP from same-scene (>= 0.90) images: "
          f"{share:.1%} of images x {nano_gap - zs_gap:+.4f} ~ {share * (nano_gap - zs_gap):+.4f}")


if __name__ == "__main__":
    main()
