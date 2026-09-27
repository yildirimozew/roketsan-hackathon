"""Predict with a trained YOLO model on a manifest of train or test image IDs.

conf 0.001, max_det 1000, one image at a time; boxes clipped at the image edge to zero width or height are
dropped. Output: image_id,label,conf,x,y,w,h (the format evaluate.py and the fusion read).

Test-time augmentation: --augment uses Ultralytics' built-in TTA (left-right flip and scales 1, 0.83, 0.67 of
imgsz, merged by its NMS); --hflip predicts on the mirrored image and maps the boxes back (one view; fuse views
afterwards, e.g. with WBF).

Usage: python ardahan/predict_yolo.py WEIGHTS --images splits/scene_holdout_v2/val.txt --out preds.csv
       [--split train|test] [--imgsz 1280] [--augment | --hflip]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["car", "van", "truck", "bus"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("weights")
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default="train", choices=["train", "test"])
    ap.add_argument("--imgsz", type=int, default=1280)
    tta = ap.add_mutually_exclusive_group()
    tta.add_argument("--augment", action="store_true", help="Ultralytics built-in TTA")
    tta.add_argument("--hflip", action="store_true", help="predict on the mirrored image, boxes mapped back")
    a = ap.parse_args()
    ids = (ROOT / a.images).read_text().split()
    model = YOLO(a.weights)
    assert list(model.names.values()) == CLASSES, model.names
    rows = []
    for iid in ids:
        path = ROOT / f"data/{a.split}/images/{iid}.jpg"
        src = str(path)
        if a.hflip:
            im = Image.open(path).convert("RGB")
            width = im.width
            src = np.ascontiguousarray(np.asarray(im)[:, ::-1, ::-1])  # mirrored, RGB -> BGR as Ultralytics expects
        r = model.predict(src, imgsz=a.imgsz, conf=0.001, iou=0.7, max_det=1000, half=True, verbose=False,
                          device=0, augment=a.augment)[0]
        for (x1, y1, x2, y2), c, s in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
            if a.hflip:
                x1, x2 = width - x2, width - x1
            if x2 - x1 >= 1 and y2 - y1 >= 1:
                rows.append((iid, CLASSES[int(c)], round(s, 5), round(x1, 1), round(y1, 1),
                             round(x2 - x1, 1), round(y2 - y1, 1)))
    df = pd.DataFrame(rows, columns=["image_id", "label", "conf", "x", "y", "w", "h"])
    df.to_csv(a.out, index=False)
    print(f"{len(df)} boxes on {df.image_id.nunique()} of {len(ids)} images -> {a.out}")


if __name__ == "__main__":
    main()
