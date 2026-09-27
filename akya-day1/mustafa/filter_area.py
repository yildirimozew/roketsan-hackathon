"""Drop boxes with implausible pixel area (w*h), plus non-positive w/h.

  python mustafa/filter_area.py --inp X.csv --out Y.csv [--min-area 100 --max-area 500000]
Train GT areas span 200..328,640 px² (12 boxes > 250k, half of them buses), hence the 500k default.
"""
import argparse
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--inp", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--min-area", type=float, default=100); ap.add_argument("--max-area", type=float, default=500000)
a = ap.parse_args()

p = pd.read_csv(a.inp)
area = p.w * p.h
keep = (p.w > 0) & (p.h > 0) & area.between(a.min_area, a.max_area)
p[keep].to_csv(a.out, index=False)
print(f"{a.inp}: kept {keep.sum()}/{len(p)} (too small {(area < a.min_area).sum()}, too large {(area > a.max_area).sum()}) -> {a.out}")
