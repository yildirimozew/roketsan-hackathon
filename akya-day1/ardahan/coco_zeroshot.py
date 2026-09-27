"""Pipeline check, not a model: COCO-pretrained YOLO11m, no training, on fold-1 val and test.

COCO car/truck/bus -> car/truck/bus; van has no COCO class and is never predicted.
Inference at conf 0.001, max_det 1000. Writes to ardahan/outputs/coco_zeroshot/:
  preds_val_fold1.csv, preds_test.csv   image_id,label,conf,x,y,w,h
  submission.csv                        competition format
  overlay_*.jpg                         ground truth drawn from the converted YOLO labels (green)
                                        and predictions with conf >= 0.3 (red)

Usage: python ardahan/coco_zeroshot.py [--imgsz 1280]   (from the repo root)
"""
import argparse
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
YOLO_DS = ROOT / "ardahan/outputs/yolo_ds"
OUT = ROOT / "ardahan/outputs/coco_zeroshot"
WEIGHTS = ROOT / "ardahan/outputs/kaggle_deps/yolo11m.pt"
COCO_TO_OURS = {2: "car", 7: "truck", 5: "bus"}
CLASSES = ["car", "van", "truck", "bus"]


def predict(model, paths, imgsz):
    rows = []
    for p in paths:  # one at a time: a list source is predicted as a single batch
        r = model.predict(str(p), imgsz=imgsz, conf=0.001, iou=0.7, max_det=1000,
                          classes=list(COCO_TO_OURS), half=True, verbose=False, device=0)[0]
        iid = Path(r.path).stem
        for (x1, y1, x2, y2), c, s in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
            rows.append((iid, COCO_TO_OURS[int(c)], round(s, 5), round(x1, 1), round(y1, 1),
                         round(x2 - x1, 1), round(y2 - y1, 1)))
    return pd.DataFrame(rows, columns=["image_id", "label", "conf", "x", "y", "w", "h"])


def to_submission(preds, ids):
    s = (preds.label + " " + preds.conf.astype(str) + " " + preds.x.astype(str) + " " + preds.y.astype(str)
         + " " + preds.w.astype(str) + " " + preds.h.astype(str))
    strings = s.groupby(preds.image_id).agg(" ".join)
    return pd.DataFrame({"image_id": ids, "PredictionString": [strings.get(i, "none") for i in ids]})


def overlay(iid, preds, path):
    im = Image.open(YOLO_DS / f"images/train/{iid}.jpg").convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im)
    for line in (YOLO_DS / f"labels/train/{iid}.txt").read_text().split("\n"):
        if not line:
            continue
        c, cx, cy, w, h = line.split()
        cx, cy, w, h = float(cx) * W, float(cy) * H, float(w) * W, float(h) * H
        d.rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], outline=(0, 255, 0), width=2)
        d.text((cx - w / 2, cy - h / 2 - 11), CLASSES[int(c)], fill=(0, 255, 0))
    for r in preds[(preds.image_id == iid) & (preds.conf >= 0.3)].itertuples():
        d.rectangle([r.x, r.y, r.x + r.w, r.y + r.h], outline=(255, 0, 0), width=2)
        d.text((r.x, r.y + r.h + 1), f"{r.label} {r.conf:.2f}", fill=(255, 0, 0))
    im.save(path, quality=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imgsz", type=int, default=1280)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(WEIGHTS))

    val_ids = (ROOT / "splits/folds/fold_1_val.txt").read_text().split()
    val = predict(model, [DATA / f"train/images/{i}.jpg" for i in val_ids], a.imgsz)
    val.to_csv(OUT / "preds_val_fold1.csv", index=False)
    print(f"val: {len(val)} boxes on {val.image_id.nunique()} of {len(val_ids)} images", flush=True)

    # three val images with a bus, a truck and a van in the ground truth
    ann = pd.read_csv(DATA / "train/annotations.csv")
    ann = ann[ann.image_id.isin(val_ids)]
    for lab in ["bus", "truck", "van"]:
        iid = ann[ann.label == lab].image_id.value_counts().index[5]
        overlay(iid, val, OUT / f"overlay_{lab}_{iid}.jpg")

    sample = pd.read_csv(DATA / "sample_submission.csv")
    test = predict(model, [DATA / f"test/images/{i}.jpg" for i in sample.image_id], a.imgsz)
    test.to_csv(OUT / "preds_test.csv", index=False)
    to_submission(test, list(sample.image_id)).to_csv(OUT / "submission.csv", index=False)
    print(f"test: {len(test)} boxes on {test.image_id.nunique()} of {len(sample)} images -> {OUT / 'submission.csv'}")


if __name__ == "__main__":
    main()
