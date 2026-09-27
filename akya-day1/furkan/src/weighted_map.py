"""mAP@0.5 evaluator that mimics the Kaggle metric, with optional per-image weights.

Kaggle rule (competition page): a prediction is a TP if the class matches and IoU >= 0.5
with a not-yet-matched ground-truth box; predictions are ranked by confidence per class;
AP is computed per class and the score is the mean over car, van, truck, bus.

AP uses all-point interpolation (VOC2010+/COCO-style envelope). Without weights this is the
standard metric. With `image_weights`, every TP/FP and every GT box of an image counts
`w_image` times. This lets us reweight the shared validation split so that its resolution
mix matches the test set (see furkan/notebooks/01b_eda_addendum.ipynb).

Boxes are pandas DataFrames with columns: image_id, label, x, y, w, h  (+ conf for preds),
x/y = top-left corner in pixels, same as annotations.csv and the submission format.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CLASSES = ["car", "van", "truck", "bus"]


def _iou_one_to_many(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[0] + box[2], boxes[:, 0] + boxes[:, 2])
    y2 = np.minimum(box[1] + box[3], boxes[:, 1] + boxes[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    union = box[2] * box[3] + boxes[:, 2] * boxes[:, 3] - inter
    return inter / np.maximum(union, 1e-9)


def average_precision(recall: np.ndarray, precision: np.ndarray) -> float:
    """All-point interpolated area under the precision-recall curve."""
    mrec = np.concatenate([[0.0], recall, [1.0]])
    mpre = np.concatenate([[0.0], precision, [0.0]])
    mpre = np.maximum.accumulate(mpre[::-1])[::-1]
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


def evaluate(
    gt: pd.DataFrame,
    pred: pd.DataFrame,
    image_ids=None,
    image_weights: dict | pd.Series | None = None,
    iou_thr: float = 0.5,
    classes=CLASSES,
) -> dict:
    """Return {"mAP": float, "AP": {class: float}, "n_gt": {class: float}}.

    image_ids: images that belong to the evaluated set (images without GT still count, so
    false positives on background images are penalised). Defaults to images in `gt`.
    image_weights: optional mapping image_id -> weight (missing ids get weight 1).
    """
    if image_ids is None:
        image_ids = gt["image_id"].unique()
    ids = pd.Index(pd.unique(np.asarray(image_ids)))
    w = pd.Series(1.0, index=ids)
    if image_weights is not None:
        w.update(pd.Series(image_weights, dtype=float))
    gt = gt[gt["image_id"].isin(ids)]
    pred = pred[pred["image_id"].isin(ids)]

    ap, n_gt = {}, {}
    for c in classes:
        g = gt[gt["label"] == c]
        p = pred[pred["label"] == c].sort_values("conf", ascending=False, kind="mergesort")
        g_boxes = {k: v[["x", "y", "w", "h"]].to_numpy(float) for k, v in g.groupby("image_id")}
        used = {k: np.zeros(len(v), bool) for k, v in g_boxes.items()}
        npos = float(w.reindex(g["image_id"]).sum())
        n_gt[c] = npos
        if npos == 0:
            ap[c] = float("nan")
            continue
        tp = np.zeros(len(p))
        fp = np.zeros(len(p))
        pw = w.reindex(p["image_id"]).to_numpy()
        for k, (img, box) in enumerate(zip(p["image_id"].to_numpy(),
                                           p[["x", "y", "w", "h"]].to_numpy(float))):
            cand = g_boxes.get(img)
            if cand is None:
                fp[k] = pw[k]
                continue
            ious = _iou_one_to_many(box, cand)
            ious[used[img]] = -1.0          # each GT can be matched once
            j = int(np.argmax(ious))
            if ious[j] >= iou_thr:
                used[img][j] = True
                tp[k] = pw[k]
            else:
                fp[k] = pw[k]
        ctp, cfp = np.cumsum(tp), np.cumsum(fp)
        recall = ctp / npos
        precision = ctp / np.maximum(ctp + cfp, 1e-12)
        ap[c] = average_precision(recall, precision)
    vals = [v for v in ap.values() if not np.isnan(v)]
    return {"mAP": float(np.mean(vals)) if vals else float("nan"), "AP": ap, "n_gt": n_gt}


def test_weights_for(val_ids, resolution_of: dict, test_share: dict) -> pd.Series:
    """Per-image weights that make the val resolution mix equal to the test mix.

    weight(img) = P_test(res) / P_val(res); resolutions absent from the test get weight 0.
    """
    res = pd.Series({i: resolution_of[i] for i in val_ids})
    val_share = res.value_counts(normalize=True)
    ratio = {r: test_share.get(r, 0.0) / val_share[r] for r in val_share.index}
    return res.map(ratio).astype(float)
