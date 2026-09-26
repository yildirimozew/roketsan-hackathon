"""TTA views x models x WBF settings on scene_holdout_v2 val: which fusion to put the crop classifier on.

Views per model (ardahan/predict_yolo.py): plain and --hflip at 1280 and 1536, and Ultralytics' --augment at 1280.
Candidates: each model's 4 and 5 views, and both models together (8 and 10 views), fused with fuse_wbf.fuse
(equal weights, conf_type 'avg'); the two-model fusions at several WBF IoUs. Each is scored with evaluate.py on all
of v2 val, on its two scene-group halves and with val_strata weights. Pick on the halves: a candidate should beat
the others on both. Writes DIR/combos.csv and the fused predictions of every candidate (fused_<name>.csv).

Usage: python ardahan/tta_combos.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ardahan"))
from crop_classifier import SPLIT, scene_halves  # noqa: E402
from evaluate import evaluate  # noqa: E402
from fuse_wbf import fuse  # noqa: E402
from leakage_map import PerImage  # noqa: E402

OUT = ROOT / "ardahan/outputs/tta_combos"
MODELS = {"sh2": ROOT / "ardahan/outputs/tta_yolo11m_sh2", "rfs": ROOT / "ardahan/outputs/tta_yolo11m_sh2_rfs"}
V4 = ["plain1280", "hflip1280", "plain1536", "hflip1536"]
V5 = V4 + ["augment1280"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ids = (SPLIT / "val.txt").read_text().split()
    gt = pd.read_csv(ROOT / "data/train/annotations.csv")
    halves = scene_halves(ids)
    st = pd.read_csv(SPLIT / "val_strata.csv").set_index("image_id").loc[ids]
    sz = pd.read_csv(ROOT / "ardahan/image_sizes_train.csv").set_index("image_id")
    sizes = {i: (int(sz.width[i]), int(sz.height[i])) for i in ids}
    view = {(m, v): pd.read_csv(d / f"val_{v}.csv") for m, d in MODELS.items() for v in V5}

    specs = [(f"{m} {len(vs)}v", [(m, v) for v in vs], 0.6) for m in MODELS for vs in (V4, V5)]
    for vs in (V4, V5):
        for t in (0.55, 0.6, 0.7):
            specs.append((f"sh2+rfs {2 * len(vs)}v @{t}", [(m, v) for m in MODELS for v in vs], t))
    rows = []
    for name, parts, t in specs:
        p = fuse([view[k] for k in parts], [1.0] * len(parts), t, ids, sizes)
        p.to_csv(OUT / f"fused_{name.replace(' ', '_').replace('+', '_').replace('@', 'iou')}.csv", index=False)
        r = evaluate(gt, p, ids)
        h = [evaluate(gt, p, x)["mAP50"] for x in halves]
        wm = PerImage(gt, p, ids).ap(ids, st.weight.to_dict())["mAP"]
        rows.append({"candidate": name, "iou": t, "mAP": r["mAP50"], "weighted": wm, "half0": h[0], "half1": h[1],
                     **r["AP"]})
        print(f"{name:22s} mAP {r['mAP50']:.4f}  weighted {wm:.4f}  halves {h[0]:.4f} / {h[1]:.4f}  " +
              " ".join(f"{c} {v:.3f}" for c, v in r["AP"].items()), flush=True)
    t = pd.DataFrame(rows).sort_values("mAP", ascending=False)
    t.to_csv(OUT / "combos.csv", index=False)
    print("\n" + t.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
