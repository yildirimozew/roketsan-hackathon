"""Prediction CSV (image_id,label,conf,x,y,w,h) -> Kaggle submission (image_id,PredictionString), then validate.

  python mustafa/format_submission.py --inp mustafa/preds/test_preds.csv --out mustafa/preds/submission.csv
Rows follow data/sample_submission.csv order; images without boxes get "none"; max 1000 boxes/image by conf.
"""
import argparse, subprocess, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--inp", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--sample", default=str(ROOT / "data/sample_submission.csv"))
a = ap.parse_args()

p = pd.read_csv(a.inp)
p["image_id"] = p["image_id"].astype(str); p["label"] = p["label"].str.lower()
bad = ~p.label.isin(["car", "van", "truck", "bus"]) | (p.w <= 0) | (p.h <= 0) | p[["conf", "x", "y", "w", "h"]].isna().any(axis=1)
p = p[~bad].assign(conf=p.conf.clip(0, 1))
p = p.sort_values(["image_id", "conf"], ascending=[True, False]).groupby("image_id").head(1000)
p["s"] = p.label + " " + p.conf.map("{:.5f}".format) + " " + p[["x", "y", "w", "h"]].apply(lambda r: " ".join(f"{v:.1f}" for v in r), axis=1)
ps = p.groupby("image_id", sort=False)["s"].agg(" ".join)

ids = pd.read_csv(a.sample, dtype=str)["image_id"]
extra = set(ps.index) - set(ids)
print(f"{len(p)} boxes kept, {bad.sum()} invalid dropped, {len(extra)} image_ids not in sample (ignored), "
      f"{(~ids.isin(ps.index)).sum()} sample images -> none", flush=True)
pd.DataFrame({"image_id": ids, "PredictionString": ids.map(ps).fillna("none")}).to_csv(a.out, index=False)
sys.exit(subprocess.call([sys.executable, str(ROOT / "ardahan/check_submission.py"), a.out]))
