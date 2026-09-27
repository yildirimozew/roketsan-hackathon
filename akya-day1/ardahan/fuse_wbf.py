"""Weighted box fusion (ZFTurbo's ensemble_boxes) of YOLO11m and RF-DETR Large, both trained on fold-1 train.

Validation is committed fold-1 val: the only set neither model trained on (scene_holdout_v1 val is 81%
inside their training data).

RF-DETR: its merged file (merged_predictions.json) caps images at 500 detections (937 of 1,295 images hit
the cap). Its merge is reproduced from the raw tile predictions (boxes owned by their tile, class-wise NMS
at IoU 0.6, which reproduces the merged file) with the cap raised to 1000. Its per-tile output stops at
score ~0.0025, so conf 0.001 cannot be reached without re-running it.

Fusion: weights proportional to each model's val mAP (evaluate.py), conf_type 'avg', skip_box_thr 0.001,
top 1000 per image after fusion. iou_thr swept over 0.50/0.55/0.60/0.65 and picked on val; the pick is
compared to the best single model with a paired bootstrap over images.

The chosen settings are written to ardahan/wbf_config.json; `submit` applies them to test predictions.

Usage:
  python ardahan/fuse_wbf.py val        (tune on fold-1 val; writes ardahan/wbf_config.json)
  python ardahan/fuse_wbf.py submit --yolo YOLO_TEST.csv --rfdetr-npz RAW_TILES.npz          --rfdetr-annotations TEST_IMAGES.coco.json --out submission.csv [--split test]
    YOLO_TEST.csv: image_id,label,conf,x,y,w,h from the YOLO11m checkpoint (conf 0.001, max_det 1000)
    RAW_TILES.npz / *.coco.json: RF-DETR raw tile output and its image-id mapping, in the same format as
      the fold-1 val files (image_ids, boxes xyxy in full-image pixels, scores, labels 0-3, owners)
  Add --images MANIFEST --split train to fuse a validation set instead (it is then scored).
"""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ardahan/outputs/wbf"
RF = ROOT / "ardahan/outputs/rfdetr_large_fold1"
MED = ROOT / "ardahan/outputs/kaggle_yolo11m_baseline"
CLASSES = ["car", "van", "truck", "bus"]
COLS = ["image_id", "label", "conf", "x", "y", "w", "h"]
MAX_DETS = 1000
CONFIG = ROOT / "ardahan/wbf_config.json"


def rfdetr_from_merged(pred_path=RF / "merged_predictions.json", ann_path=RF / "validation_annotations.coco.json"):
    ann = json.load(open(ann_path))
    idmap = {im["id"]: im["original_image_id"] for im in ann["images"]}
    names = {c["id"]: c["name"] for c in ann["categories"]}
    p = json.load(open(pred_path))
    return pd.DataFrame([(idmap[r["image_id"]], names[r["category_id"]], r["score"], *r["bbox"]) for r in p], columns=COLS)


def rfdetr_from_raw(cap, npz_path=RF / "raw_tile_predictions.npz", ann_path=RF / "validation_annotations.coco.json"):
    """Yildirim's merge (tile-owned boxes, class-wise NMS at IoU 0.6), with the per-image cap as a parameter."""
    import torch
    from torchvision.ops import batched_nms
    ann = json.load(open(ann_path))
    idmap = {im["id"]: im["original_image_id"] for im in ann["images"]}
    names = {c["id"]: c["name"] for c in ann["categories"]}
    assert [names[k] for k in sorted(names)] == CLASSES, names
    z = np.load(npz_path)
    own = z["owners"]
    ids, b, s, lab = z["image_ids"][own], z["boxes"][own], z["scores"][own], z["labels"][own].astype(np.int64)
    rows = []
    order = np.argsort(ids, kind="stable")
    ids, b, s, lab = ids[order], b[order], s[order], lab[order]
    starts = np.r_[0, np.nonzero(np.diff(ids))[0] + 1, len(ids)]
    for a, e in zip(starts[:-1], starts[1:]):
        keep = batched_nms(torch.tensor(b[a:e]), torch.tensor(s[a:e]), torch.tensor(lab[a:e]), 0.6)[:cap].numpy()
        bb = b[a:e][keep]
        rows.append(pd.DataFrame({"image_id": idmap[int(ids[a])], "label": [CLASSES[k] for k in lab[a:e][keep]],
                                  "conf": s[a:e][keep], "x": bb[:, 0], "y": bb[:, 1],
                                  "w": bb[:, 2] - bb[:, 0], "h": bb[:, 3] - bb[:, 1]}))
    df = pd.concat(rows, ignore_index=True)
    return df[(df.w >= 1) & (df.h >= 1)]


def _fuse_one(args):
    from ensemble_boxes import weighted_boxes_fusion
    iid, W, H, parts, weights, iou_thr = args
    boxes, scores, labels = [], [], []
    for p in parts:
        x1 = np.clip(p[:, 0] / W, 0, 1)
        y1 = np.clip(p[:, 1] / H, 0, 1)
        x2 = np.clip((p[:, 0] + p[:, 2]) / W, 0, 1)
        y2 = np.clip((p[:, 1] + p[:, 3]) / H, 0, 1)
        boxes.append(np.stack([x1, y1, x2, y2], 1).tolist())
        scores.append(p[:, 4].tolist())
        labels.append(p[:, 5].tolist())
    if not any(len(s) for s in scores):
        return []
    fb, fs, fl = weighted_boxes_fusion(boxes, scores, labels, weights=weights, iou_thr=iou_thr,
                                       skip_box_thr=0.001, conf_type="avg")
    o = np.argsort(-fs)[:MAX_DETS]
    fb, fs, fl = fb[o], fs[o], fl[o]
    return [(iid, CLASSES[int(c)], round(float(s), 5), round(b[0] * W, 1), round(b[1] * H, 1),
             round((b[2] - b[0]) * W, 1), round((b[3] - b[1]) * H, 1)) for b, s, c in zip(fb, fs, fl)
            if (b[2] - b[0]) * W >= 1 and (b[3] - b[1]) * H >= 1]


def fuse(preds_list, weights, iou_thr, image_ids, sizes):
    enc = []
    for p in preds_list:
        q = p.assign(c=p.label.map({c: i for i, c in enumerate(CLASSES)}))
        enc.append({iid: g[["x", "y", "w", "h", "conf", "c"]].to_numpy(float) for iid, g in q.groupby("image_id")})
    empty = np.zeros((0, 6))
    jobs = [(iid, *sizes[iid], [e.get(iid, empty) for e in enc], weights, iou_thr) for iid in image_ids]
    rows = []
    with ProcessPoolExecutor(14) as ex:
        for r in ex.map(_fuse_one, jobs, chunksize=16):
            rows += r
    return pd.DataFrame(rows, columns=COLS)


def main():
    import sys
    sys.path.insert(0, str(ROOT / "ardahan"))
    from evaluate import evaluate
    from leakage_map import PerImage, boot

    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["val", "submit"])
    ap.add_argument("--yolo")
    ap.add_argument("--rfdetr-npz")
    ap.add_argument("--rfdetr-annotations")
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--images", help="manifest of image ids; default: data/sample_submission.csv")
    ap.add_argument("--split", default="test", choices=["train", "test"])
    ap.add_argument("--out", default="submission.csv")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    gt = pd.read_csv(ROOT / "data/train/annotations.csv")
    sizes = pd.read_csv(ROOT / "ardahan/image_sizes_train.csv").set_index("image_id")
    sizes = {i: (r.width, r.height) for i, r in sizes.iterrows()}
    f1 = (ROOT / "splits/folds/fold_1_val.txt").read_text().split()

    if a.step == "submit":
        return submit(a, gt)

    med = pd.read_csv(MED / "preds_val_fold1.csv")
    med = med[(med.w >= 1) & (med.h >= 1)]
    rf_file = rfdetr_from_merged()
    rf500, rf1000 = rfdetr_from_raw(500), rfdetr_from_raw(1000)
    rf1000.to_csv(OUT / "rfdetr_val_fold1_cap1000.csv", index=False)
    fmt = lambda r: f"mAP {r['mAP50']:.4f}   " + "  ".join(f"{c} {r['AP'][c]:.4f}" for c in CLASSES)  # noqa: E731
    print("## single models on committed fold-1 val (evaluate.py)")
    res = {}
    for name, p in [("YOLO11m", med), ("RF-DETR, his merged file (cap 500)", rf_file),
                    ("RF-DETR, re-merged cap 500", rf500), ("RF-DETR, re-merged cap 1000", rf1000)]:
        res[name] = evaluate(gt, p, f1)
        print(f"  {name:36s} {fmt(res[name])}   ({len(p) / len(f1):.0f} boxes/img)")
    rf = rf1000
    w_med, w_rf = res["YOLO11m"]["mAP50"], res["RF-DETR, re-merged cap 1000"]["mAP50"]
    weights = [w_med / (w_med + w_rf), w_rf / (w_med + w_rf)]
    best_name = max(["YOLO11m", "RF-DETR, re-merged cap 1000"], key=lambda k: res[k]["mAP50"])
    best_preds = med if best_name == "YOLO11m" else rf
    print(f"\nWBF weights (proportional to val mAP): YOLO11m {weights[0]:.3f}, RF-DETR {weights[1]:.3f}; "
          f"best single model: {best_name}")

    print("\n## WBF on fold-1 val, conf_type avg")
    fused = {}
    for t in [0.50, 0.55, 0.60, 0.65]:
        fused[t] = fuse([med, rf], weights, t, f1, sizes)
        fused[t].to_csv(OUT / f"wbf_val_fold1_iou{t:.2f}.csv", index=False)
        print(f"  iou_thr {t:.2f}   {fmt(evaluate(gt, fused[t], f1))}", flush=True)
    t_best = max(fused, key=lambda t: evaluate(gt, fused[t], f1)["mAP50"])
    pf, pb = PerImage(gt, fused[t_best], f1), PerImage(gt, best_preds, f1)
    d = pf.ap(f1)["mAP"] - pb.ap(f1)["mAP"]
    lo, hi = boot(lambda g: pf.ap(g[0])["mAP"] - pb.ap(g[0])["mAP"], [f1], n=500)
    print(f"\nbest iou_thr on val: {t_best:.2f}")
    print(f"fused - {best_name}: {d:+.4f}  (paired bootstrap over images, 95% CI {lo:+.4f} .. {hi:+.4f})")
    print("verdict:", "fusion beats the best single model" if lo > 0 else "fusion does NOT clearly beat the best single model")
    (OUT / "val_summary.json").write_text(json.dumps({"weights": weights, "iou_thr": t_best, "delta": d,
                                                       "ci": [lo, hi], "best_single": best_name}, indent=2))
    CONFIG.write_text(json.dumps({
        "models": ["yolo11m (ardahan/kaggle/yolo11m_baseline, last.pt)", "rf-detr large (checkpoint_best_ema.pth)"],
        "weights": [round(w, 6) for w in weights], "iou_thr": t_best, "conf_type": "avg", "skip_box_thr": 0.001,
        "max_dets_per_image": MAX_DETS,
        "rfdetr_merge": {"owners_only": True, "classwise_nms_iou": 0.6, "max_dets_per_image": MAX_DETS},
        "validation": {"split": "splits/folds/fold_1_val.txt", "fused_mAP50": round(pf.ap(f1)["mAP"], 4),
                       "best_single": best_name, "best_single_mAP50": round(pb.ap(f1)["mAP"], 4),
                       "delta_95ci": [round(lo, 4), round(hi, 4)]},
    }, indent=2) + "\n")
    print(f"settings -> {CONFIG}")


def submit(a, gt):
    """Fuse YOLO11m and RF-DETR predictions with the settings in the config; write and check a submission."""
    from PIL import Image

    from check_submission import check
    from evaluate import evaluate
    cfg = json.loads(Path(a.config).read_text())
    if a.images:
        ids = Path(a.images).read_text().split()
    else:
        ids = list(pd.read_csv(ROOT / "data/sample_submission.csv").image_id)
    sizes = {}
    for iid in ids:
        with Image.open(ROOT / f"data/{a.split}/images/{iid}.jpg") as im:
            sizes[iid] = im.size
    yolo = pd.read_csv(a.yolo)
    yolo = yolo[(yolo.w >= 1) & (yolo.h >= 1)]
    rf = rfdetr_from_raw(cfg["rfdetr_merge"]["max_dets_per_image"], a.rfdetr_npz, a.rfdetr_annotations)
    for name, p in [("yolo", yolo), ("rf-detr", rf)]:
        missing = set(ids) - set(p.image_id)
        extra = set(p.image_id) - set(ids)
        print(f"{name}: {len(p)} boxes, {len(set(ids)) - len(missing)} of {len(ids)} images have boxes, "
              f"{len(extra)} ids outside the image list")
        assert not extra, f"{name} predictions contain image ids that are not in the image list"
    fused = fuse([yolo, rf], cfg["weights"], cfg["iou_thr"], ids, sizes)
    print(f"fused: {len(fused)} boxes; weights {cfg['weights']}, iou_thr {cfg['iou_thr']}")
    if a.split == "train":
        r = evaluate(gt, fused, ids)
        print(f"mAP@0.5 {r['mAP50']:.4f}  " + "  ".join(f"{c} {v:.4f}" for c, v in r["AP"].items()))
        fused.to_csv(a.out, index=False)
        return
    s = (fused.label + " " + fused.conf.astype(str) + " " + fused.x.astype(str) + " " + fused.y.astype(str)
         + " " + fused.w.astype(str) + " " + fused.h.astype(str)).groupby(fused.image_id).agg(" ".join)
    pd.DataFrame({"image_id": ids, "PredictionString": [s.get(i, "none") for i in ids]}).to_csv(a.out, index=False)
    errs = check(a.out)
    print(f"-> {a.out}: " + ("check_submission OK" if not errs else "check_submission FAILED:\n  " + "\n  ".join(errs)))


if __name__ == "__main__":
    main()
