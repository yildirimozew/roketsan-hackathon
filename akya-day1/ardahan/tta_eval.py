"""Test-time augmentation for a YOLO model: score single views and WBF fusions of views on scene_holdout_v2 val.

Views are prediction CSVs from ardahan/predict_yolo.py (plain, --hflip, --augment, other --imgsz). Fusions use
fuse_wbf.fuse (conf_type 'avg', skip 0.001, top 1000 per image), equal view weights, iou_thr swept.

Every candidate is scored with evaluate.py on the two scene-group halves of v2 val (crop_classifier.scene_halves)
and on all of it. A candidate is only credible if it beats the plain view on both halves; the table also gives a
scene-group bootstrap CI of the change against the plain view on the full set.

Usage: python ardahan/tta_eval.py --dir ardahan/outputs/tta_yolo11m_sh2 --plain val_plain1280.csv
       [--fuse val_plain1280.csv+val_hflip1280.csv ...] [--save NAME]  (--save writes that candidate's CSV)
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ardahan"))
from crop_classifier import SPLIT, boot, scene_halves  # noqa: E402
from evaluate import CLASSES, evaluate  # noqa: E402
from fuse_wbf import fuse  # noqa: E402
from leakage_map import PerImage  # noqa: E402

IOU_THRS = (0.55, 0.6, 0.7)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--plain", required=True, help="the no-TTA view, the baseline")
    ap.add_argument("--fuse", nargs="*", default=[], help="view combinations joined with +")
    ap.add_argument("--save", help="write this candidate's predictions to DIR/<name>.csv")
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    d = ROOT / a.dir
    ids = (SPLIT / "val.txt").read_text().split()
    gt = pd.read_csv(ROOT / "data/train/annotations.csv")
    g = pd.read_csv(SPLIT / "groups.csv")
    grp = dict(zip(g.image_id, g.scene_group))
    halves = scene_halves(ids)
    sz = pd.read_csv(ROOT / "ardahan/image_sizes_train.csv").set_index("image_id")
    sizes = {i: (int(sz.width[i]), int(sz.height[i])) for i in ids}
    load = {f.name: pd.read_csv(f) for f in sorted(d.glob("val_*.csv"))}

    cands = {n: p for n, p in load.items()}
    for combo in a.fuse:
        parts = combo.split("+")
        for t in IOU_THRS:
            cands[f"wbf[{combo}]@{t}"] = fuse([load[p] for p in parts], [1.0] * len(parts), t, ids, sizes)

    rows = []
    base = PerImage(gt, load[a.plain], ids)
    for n, p in cands.items():
        r = evaluate(gt, p, ids)
        h = [evaluate(gt, p, hh)["mAP50"] for hh in halves]
        rows.append({"candidate": n, "mAP": r["mAP50"], **r["AP"], "half0": h[0], "half1": h[1]})
        print(f"{n:55s} mAP {r['mAP50']:.4f}  halves {h[0]:.4f} / {h[1]:.4f}", flush=True)
    t = pd.DataFrame(rows).set_index("candidate")
    b = t.loc[a.plain]
    t["d_mAP"] = t.mAP - b.mAP
    t["d_half0"], t["d_half1"] = t.half0 - b.half0, t.half1 - b.half1
    t["wins_both"] = (t.d_half0 > 0) & (t.d_half1 > 0)
    t = t.sort_values("mAP", ascending=False)
    t.to_csv(d / "tta_table.csv")
    print("\n" + t.round(4).to_string())

    best = t.index[0] if a.save is None else a.save
    if best != a.plain:
        r = boot(base, PerImage(gt, cands[best], ids), ids, grp, n=a.boot)
        print(f"\n{best} vs {a.plain} on v2 val ({len(ids)} images), 95% scene-bootstrap CI:")
        for c in CLASSES + ["mAP"]:
            x = r[c]
            print(f"  {c:6s} {x['before']:.4f} -> {x['after']:.4f}  {x['delta']:+.4f}  "
                  f"[{x['ci'][0]:+.4f}, {x['ci'][1]:+.4f}]")
    if a.save:
        out = d / f"{a.save.replace('[', '_').replace(']', '').replace('+', '_').replace('@', '_iou')}.csv"
        cands[a.save].to_csv(out, index=False)
        print(f"saved {out}")


if __name__ == "__main__":
    main()
