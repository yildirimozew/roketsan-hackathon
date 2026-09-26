"""Score prediction CSVs: ardahan/evaluate.py mAP@0.5 + test-weighted mAP (val_strata.csv weights)."""
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ardahan"))
from evaluate import evaluate, read_preds  # noqa: E402

CLASSES = ["car", "van", "truck", "bus"]

def weighted_map(preds, gt, w):
    """Image-weighted VOC-style AP@0.5 (same logic as yildirim/one_hour_models/evaluate_yolo_sliced.weighted_map)."""
    aps = {}
    for c in CLASSES:
        g = gt[gt.label == c]
        pos = w.reindex(g.image_id).sum()
        boxes = {i: d[["x", "y", "w", "h"]].to_numpy(float) for i, d in g.groupby("image_id")}
        used = {i: np.zeros(len(b), bool) for i, b in boxes.items()}
        r = preds[preds.label == c].sort_values("conf", ascending=False, kind="mergesort")
        tp, fp = np.zeros(len(r)), np.zeros(len(r))
        for k, (iid, x, y, bw, bh) in enumerate(zip(r.image_id, r.x, r.y, r.w, r.h)):
            wt = w[iid]; b = boxes.get(iid)
            if b is None: fp[k] = wt; continue
            ix = np.clip(np.minimum(x + bw, b[:, 0] + b[:, 2]) - np.maximum(x, b[:, 0]), 0, None)
            iy = np.clip(np.minimum(y + bh, b[:, 1] + b[:, 3]) - np.maximum(y, b[:, 1]), 0, None)
            inter = ix * iy; iou = inter / np.maximum(bw * bh + b[:, 2] * b[:, 3] - inter, 1e-12)
            iou[used[iid]] = -1; j = int(np.argmax(iou))
            if iou[j] >= 0.5: used[iid][j] = True; tp[k] = wt
            else: fp[k] = wt
        rec = np.concatenate(([0], np.cumsum(tp) / max(pos, 1e-12), [1]))
        prec = np.concatenate(([0], np.cumsum(tp) / np.maximum(np.cumsum(tp) + np.cumsum(fp), 1e-12), [0]))
        prec = np.maximum.accumulate(prec[::-1])[::-1]; ch = np.where(rec[1:] != rec[:-1])[0]
        aps[c] = float(np.sum((rec[ch + 1] - rec[ch]) * prec[ch + 1]))
    return float(np.mean(list(aps.values()))), aps

def load_context(images=None, weights=None, annotations=None):
    """GT, image ids and test weights for a validation split."""
    ids = Path(images or ROOT / "splits/scene_holdout_v2/val.txt").read_text().split()
    gt = pd.read_csv(annotations or ROOT / "data/train/annotations.csv"); gt = gt[gt.image_id.isin(set(ids))]
    w = pd.read_csv(weights or ROOT / "splits/scene_holdout_v2/val_strata.csv").set_index("image_id")["weight"].reindex(ids).fillna(0.0)
    return gt, ids, w

def score(pr, ctx):
    """-> dict(map, wmap, car, van, truck, bus) for a preds DataFrame."""
    gt, ids, w = ctx
    pr = pr[pr.image_id.isin(set(ids))]
    r = evaluate(gt, pr, ids); wm, _ = weighted_map(pr, gt, w)
    return {"map": r["mAP50"], "wmap": wm, **{c: r["AP"][c] for c in CLASSES}}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("preds", nargs="+")
    ap.add_argument("--images"); ap.add_argument("--weights"); ap.add_argument("--annotations")
    a = ap.parse_args()
    ctx = load_context(a.images, a.weights, a.annotations)
    print("| file | mAP@0.5 | car | van | truck | bus | test-weighted |\n|---|---|---|---|---|---|---|")
    for p in a.preds:
        r = score(read_preds(p), ctx)
        print(f"| {Path(p).name} | {r['map']:.4f} | " + " | ".join(f"{r[c]:.4f}" for c in CLASSES) + f" | {r['wmap']:.4f} |")

if __name__ == "__main__":
    main()
