"""Class hedging v2: per-direction alphas, min-conf gate, IoU dedup, optional per-box class probs.

  python mustafa/hedge_classes_v2.py --inp X.csv --out Y.csv --car2van 0.1 --van2car 0.3 \
      --truck2bus 0.1 --bus2truck 0.3 --min-conf 0.05 --dedup-iou 0.7
  python mustafa/hedge_classes_v2.py --inp sub.csv --out sub_hedged.csv --config mustafa/hedge_v2_best.json
Input/output: prediction CSV (image_id,label,conf,x,y,w,h) or Kaggle submission (same format out).
"""
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hedge_classes import read_any, write_any  # noqa: E402  (v1 I/O, unchanged)

DIRS = {"car2van": ("car", "van"), "van2car": ("van", "car"), "truck2bus": ("truck", "bus"), "bus2truck": ("bus", "truck")}
DEFAULTS = {**{d: 0.0 for d in DIRS}, "min_conf": 0.05, "dedup_iou": 0.7}
MAX_PER_IMAGE = 1000


def _iou(a, b):
    """IoU matrix between xywh arrays a (n,4) and b (m,4)."""
    ix = np.clip(np.minimum(a[:, None, 0] + a[:, None, 2], b[None, :, 0] + b[None, :, 2]) - np.maximum(a[:, None, 0], b[None, :, 0]), 0, None)
    iy = np.clip(np.minimum(a[:, None, 1] + a[:, None, 3], b[None, :, 1] + b[None, :, 3]) - np.maximum(a[:, None, 1], b[None, :, 1]), 0, None)
    inter = ix * iy
    return inter / np.maximum(a[:, None, 2] * a[:, None, 3] + b[None, :, 2] * b[None, :, 3] - inter, 1e-12)


def _dup_mask(src, tgt, thr):
    """True for rows of src overlapping any tgt box of the same image with IoU >= thr."""
    dup = np.zeros(len(src), bool)
    if thr is None or src.empty or tgt.empty:
        return dup
    tgt_by = {i: g[["x", "y", "w", "h"]].to_numpy(float) for i, g in tgt.groupby("image_id", sort=False)}
    pos = np.arange(len(src))
    for iid, idx in src.groupby("image_id", sort=False).indices.items():
        tb = tgt_by.get(iid)
        if tb is not None:
            dup[pos[idx]] = (_iou(src.iloc[idx][["x", "y", "w", "h"]].to_numpy(float), tb) >= thr).any(1)
    return dup


def hedge(preds, cfg, probs=None):
    """preds: DataFrame(image_id,label,conf,x,y,w,h); cfg: DEFAULTS-shaped dict; probs: optional DataFrame p_<cls> aligned to preds."""
    cfg = {**DEFAULTS, **cfg}
    preds = preds.reset_index(drop=True)
    extra = []
    for d, (s, t) in DIRS.items():
        if not cfg[d]:
            continue
        m = (preds.label == s) & (preds.conf >= cfg["min_conf"])
        src = preds[m]
        src = src[~_dup_mask(src, preds[preds.label == t], cfg["dedup_iou"])].copy()
        src["conf"] = src["conf"] * (probs.loc[src.index, f"p_{t}"].to_numpy() if probs is not None else cfg[d])
        src["label"] = t
        extra.append(src)
    out = pd.concat([preds, *extra], ignore_index=True).sort_values(["image_id", "conf"], ascending=[True, False], kind="mergesort")
    return out.groupby("image_id", sort=False).head(MAX_PER_IMAGE).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inp", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--config", help="JSON with car2van,van2car,truck2bus,bus2truck,min_conf,dedup_iou (CLI flags override)")
    for d in DIRS:
        ap.add_argument(f"--{d}", type=float)
    ap.add_argument("--min-conf", type=float); ap.add_argument("--dedup-iou", type=float, help="<=0 disables dedup")
    ap.add_argument("--probs", help="CSV with p_car,p_van,p_truck,p_bus aligned with input rows; copy conf = conf*p(target)")
    a = ap.parse_args()
    cfg = dict(DEFAULTS)
    if a.config:
        cfg.update({k: v for k, v in json.load(open(a.config)).items() if k in DEFAULTS})
    cfg.update({k: v for k, v in {**{d: getattr(a, d) for d in DIRS}, "min_conf": a.min_conf, "dedup_iou": a.dedup_iou}.items() if v is not None})
    if cfg["dedup_iou"] is not None and cfg["dedup_iou"] <= 0:
        cfg["dedup_iou"] = None
    preds, fmt, order = read_any(a.inp)
    probs = pd.read_csv(a.probs) if a.probs else None
    if probs is not None and len(probs) != len(preds):
        ap.error(f"--probs has {len(probs)} rows, input has {len(preds)} boxes")
    out = hedge(preds, cfg, probs)
    write_any(out, fmt, order, a.out)
    print(f"{a.inp} ({fmt}, {len(preds)} boxes) -> {a.out} ({len(out)} boxes) | {cfg}")


if __name__ == "__main__":
    main()
