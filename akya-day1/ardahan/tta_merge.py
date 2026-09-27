"""Merge one model's TTA views into a single prediction CSV per split, and score the val one.

Views (from ardahan/predict_yolo.py): plain and --hflip at imgsz 1280 and 1536, in DIR/{val,test}_<view>.csv.
Merge: fuse_wbf.fuse with equal weights, conf_type 'avg', skip 0.001, top 1000 per image, IoU --iou (0.7, the value
picked for the ensemble). Val is scored with evaluate.py on splits/scene_holdout_v2/val.txt (plain, val_strata-
weighted and per class).

Usage: python ardahan/tta_merge.py --dir ardahan/outputs/tta_yolo11m_sh2_rfs_e30 --name yolo11m_sh2_rfs30
Writes ardahan/outputs/tta_merged/<name>_tta4_{val,test}.csv
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ardahan"))
from evaluate import evaluate  # noqa: E402
from fuse_wbf import fuse  # noqa: E402
from leakage_map import PerImage  # noqa: E402

VIEWS = ("plain1280", "hflip1280", "plain1536", "hflip1536")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--iou", type=float, default=0.7)
    a = ap.parse_args()
    d, out = ROOT / a.dir, ROOT / "ardahan/outputs/tta_merged"
    out.mkdir(parents=True, exist_ok=True)
    manifests = {"val": (ROOT / "splits/scene_holdout_v2/val.txt", "image_sizes_train.csv"),
                 "test": (ROOT / "ardahan/outputs/tta_yolo11m_sh2/test_ids.txt", "image_sizes_test.csv")}
    for split, (man, sizes_csv) in manifests.items():
        ids = man.read_text().split()
        sz = pd.read_csv(ROOT / "ardahan" / sizes_csv).set_index("image_id")
        sizes = {i: (int(sz.width[i]), int(sz.height[i])) for i in ids}
        views = [pd.read_csv(d / f"{split}_{v}.csv") for v in VIEWS]
        p = fuse(views, [1.0] * len(views), a.iou, ids, sizes)
        f = out / f"{a.name}_tta4_{split}.csv"
        p.to_csv(f, index=False)
        print(f"{f.relative_to(ROOT)}: {len(p)} rows on {p.image_id.nunique()} of {len(ids)} images", flush=True)
        if split == "val":
            gt = pd.read_csv(ROOT / "data/train/annotations.csv")
            st = pd.read_csv(ROOT / "splits/scene_holdout_v2/val_strata.csv").set_index("image_id").loc[ids]
            r = evaluate(gt, p, ids)
            wm = PerImage(gt, p, ids).ap(ids, st.weight.to_dict())["mAP"]
            print(f"  v2 val mAP {r['mAP50']:.4f}  weighted {wm:.4f}  " +
                  "  ".join(f"{c} {v:.4f}" for c, v in r["AP"].items()), flush=True)


if __name__ == "__main__":
    main()
