"""Local mAP@0.5 in the competition's terms, with pycocotools. Use this for decisions, not Ultralytics' val mAP.

- IoU threshold 0.5 only; mAP = mean of the four per-class APs (car, van, truck, bus), equal weight.
- areaRng [[200, 1e10]]: ground truth is all >= 200 px^2 anyway, and a prediction under 200 px^2
  that matches nothing is ignored instead of counted as a false positive, as the competition does.
- maxDets 1000 per image (COCO's 100 would truncate crowded images; the max in train is 218 boxes).
- Only images listed in the manifest are scored; an image with no predictions still counts its boxes as misses.

Predictions: a CSV of image_id,label,conf,x,y,w,h (what the kernels write), or a submission.csv
(image_id,PredictionString with "label conf x y w h" groups or "none").

Usage:
  python ardahan/evaluate.py PREDS --images splits/folds/fold_1_val.txt
  python ardahan/evaluate.py --self-test
"""
import argparse
import contextlib
import io
from pathlib import Path

import numpy as np
import pandas as pd
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["car", "van", "truck", "bus"]
MIN_AREA = 200
MAX_DETS = 1000


def read_preds(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "PredictionString" not in df.columns:
        return df[["image_id", "label", "conf", "x", "y", "w", "h"]]
    rows = []
    for iid, s in zip(df.image_id, df.PredictionString.fillna("none")):
        tok = str(s).split()
        if tok == ["none"] or not tok:
            continue
        assert len(tok) % 6 == 0, f"{iid}: PredictionString is not groups of 6"
        for k in range(0, len(tok), 6):
            rows.append((iid, tok[k], *map(float, tok[k + 1:k + 6])))
    return pd.DataFrame(rows, columns=["image_id", "label", "conf", "x", "y", "w", "h"])


def evaluate(gt: pd.DataFrame, preds: pd.DataFrame, image_ids, quiet=True) -> dict:
    """gt: image_id,x,y,w,h,label. Returns {"mAP50": float, "AP": {class: float}}."""
    image_ids = list(dict.fromkeys(image_ids))
    img_index = {iid: k + 1 for k, iid in enumerate(image_ids)}
    cat_index = {c: k + 1 for k, c in enumerate(CLASSES)}
    gt = gt[gt.image_id.isin(img_index)]
    preds = preds[preds.image_id.isin(img_index)]
    unknown = set(preds.label) - set(CLASSES)
    assert not unknown, f"unknown labels in predictions: {unknown}"

    coco_gt = COCO()
    coco_gt.dataset = {
        "images": [{"id": i} for i in img_index.values()],
        "categories": [{"id": i, "name": c} for c, i in cat_index.items()],
        "annotations": [
            {"id": k + 1, "image_id": img_index[r.image_id], "category_id": cat_index[r.label],
             "bbox": [r.x, r.y, r.w, r.h], "area": r.w * r.h, "iscrowd": 0}
            for k, r in enumerate(gt.itertuples())
        ],
    }
    with contextlib.redirect_stdout(io.StringIO()):
        coco_gt.createIndex()
    dets = [
        {"image_id": img_index[r.image_id], "category_id": cat_index[r.label],
         "bbox": [r.x, r.y, r.w, r.h], "score": r.conf}
        for r in preds.itertuples()
    ]
    if not dets:
        return {"mAP50": 0.0, "AP": {c: 0.0 for c in CLASSES}}
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        coco_dt = coco_gt.loadRes(dets)
        ev = COCOeval(coco_gt, coco_dt, "bbox")
        ev.params.imgIds = list(img_index.values())
        ev.params.iouThrs = np.array([0.5])
        ev.params.areaRng = [[MIN_AREA, 1e10]]
        ev.params.areaRngLbl = ["all"]
        ev.params.maxDets = [MAX_DETS]
        ev.evaluate()
        ev.accumulate()
    if not quiet:
        print(buf.getvalue())
    # precision: [T=1, R=101, K, A=1, M=1]; -1 where a class has no ground truth
    prec = ev.eval["precision"][0, :, :, 0, 0]
    ap = {}
    for c, k in cat_index.items():
        p = prec[:, k - 1]
        ap[c] = float(p[p > -1].mean()) if (p > -1).any() else float("nan")
    return {"mAP50": float(np.nanmean(list(ap.values()))), "AP": ap}


def self_test():
    gt = pd.DataFrame(
        [("a", 10, 10, 20, 20, "car"), ("a", 100, 100, 30, 30, "bus"), ("b", 50, 50, 20, 20, "van"),
         ("b", 0, 0, 40, 40, "truck")],
        columns=["image_id", "x", "y", "w", "h", "label"])
    P = ["image_id", "label", "conf", "x", "y", "w", "h"]
    perfect = gt.assign(conf=0.9)[P]
    r = evaluate(gt, perfect, ["a", "b"])
    assert abs(r["mAP50"] - 1) < 1e-9, r

    # an unmatched prediction under 200 px^2 must be ignored, ranked above the true one or not
    tiny = pd.concat([perfect, pd.DataFrame([("a", "car", 0.99, 300, 300, 10, 10)], columns=P)])
    assert abs(evaluate(gt, tiny, ["a", "b"])["mAP50"] - 1) < 1e-9, "sub-200 FP was counted"
    # the same false positive at 400 px^2 must cost car AP
    big = pd.concat([perfect, pd.DataFrame([("a", "car", 0.99, 300, 300, 20, 20)], columns=P)])
    r = evaluate(gt, big, ["a", "b"])
    assert r["AP"]["car"] < 1 and abs(r["AP"]["bus"] - 1) < 1e-9, r

    # IoU 0.5 boundary: 20x20 gt, prediction shifted by 5 px in x -> IoU 300/500 = 0.6 (hit); by 8 -> 0.43 (miss)
    shift = perfect.copy()
    shift.loc[shift.label == "car", "x"] += 5
    assert evaluate(gt, shift, ["a", "b"])["AP"]["car"] > 1 - 1e-9
    shift.loc[shift.label == "car", "x"] += 3
    assert evaluate(gt, shift, ["a", "b"])["AP"]["car"] == 0

    # wrong class = miss for the true class and a false positive for the predicted one
    wrong = perfect.copy()
    wrong.loc[wrong.label == "bus", "label"] = "truck"
    r = evaluate(gt, wrong, ["a", "b"])
    assert r["AP"]["bus"] == 0 and r["AP"]["truck"] < 1, r

    # an image with no predictions still counts its ground truth
    r = evaluate(gt, perfect[perfect.image_id == "a"], ["a", "b"])
    assert r["AP"]["van"] == 0 and r["AP"]["car"] > 1 - 1e-9, r

    # more than 100 detections per image are all kept (COCO's default would drop them)
    many = pd.DataFrame([("c", 40 * i, 0, 20, 20, "car") for i in range(150)], columns=gt.columns)
    r = evaluate(many, many.assign(conf=0.5)[P], ["c"])
    assert abs(r["AP"]["car"] - 1) < 1e-9, r

    # submission-string round trip
    tmp = ROOT / "ardahan/outputs/_selftest_sub.csv"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"image_id": ["a", "b"], "PredictionString": [
        "car 0.9 10 10 20 20 bus 0.8 100 100 30 30", "van 0.9 50 50 20 20 truck 0.7 0 0 40 40"]}).to_csv(tmp, index=False)
    assert abs(evaluate(gt, read_preds(tmp), ["a", "b"])["mAP50"] - 1) < 1e-9
    tmp.unlink()
    print("self-test passed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("preds", nargs="?")
    ap.add_argument("--images", help="manifest of image IDs to score (e.g. splits/folds/fold_1_val.txt)")
    ap.add_argument("--annotations", default=str(ROOT / "data/train/annotations.csv"))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.preds and a.images):
        ap.error("PREDS and --images are required")
    ids = Path(a.images).read_text().split()
    preds = read_preds(a.preds)
    missing = set(ids) - set(preds.image_id)
    r = evaluate(pd.read_csv(a.annotations), preds, ids)
    print(f"mAP@0.5 {r['mAP50']:.4f}  ({len(ids)} images, {len(missing)} with no predictions)")
    print("  " + "  ".join(f"{c} {v:.4f}" for c, v in r["AP"].items()))


if __name__ == "__main__":
    main()
