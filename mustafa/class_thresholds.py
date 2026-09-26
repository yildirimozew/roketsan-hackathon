"""Drop predictions at or below a per-class confidence threshold.

  python mustafa/class_thresholds.py --inp X.csv --out Y.csv [--car 0.30 --van 0.15 --truck 0.30 --bus 0.15]
Note: cutting boxes can only lower mAP@0.5; score the output with score_hedge.py before using it.
"""
import argparse
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--inp", required=True); ap.add_argument("--out", required=True)
for c, t in {"car": 0.30, "van": 0.15, "truck": 0.30, "bus": 0.15}.items():
    ap.add_argument(f"--{c}", type=float, default=t)
a = ap.parse_args()

p = pd.read_csv(a.inp)
keep = p.conf > p.label.str.lower().map({c: getattr(a, c) for c in ["car", "van", "truck", "bus"]}).fillna(0.0)
p[keep].to_csv(a.out, index=False)
print(f"{a.inp}: kept {keep.sum()}/{len(p)} boxes -> {a.out}\n" + p[keep].label.value_counts().to_string())
