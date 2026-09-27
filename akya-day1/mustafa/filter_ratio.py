"""Drop boxes with an extreme aspect ratio (w/h), plus non-positive w/h.

  python mustafa/filter_ratio.py --inp X.csv --out Y.csv [--min-ratio 0.1 --max-ratio 15]
Train GT ratios span 0.164..12.54 (99 boxes outside 0.2..5, mostly cut-off cars/trucks), hence the wide defaults.
"""
import argparse
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--inp", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--min-ratio", type=float, default=0.1); ap.add_argument("--max-ratio", type=float, default=15.0)
a = ap.parse_args()

p = pd.read_csv(a.inp)
ok = (p.w > 0) & (p.h > 0)
ratio = p.w / p.h.where(ok)
keep = ok & ratio.between(a.min_ratio, a.max_ratio)
p[keep].to_csv(a.out, index=False)
print(f"{a.inp}: kept {keep.sum()}/{len(p)} (too narrow {(ratio < a.min_ratio).sum()}, too wide {(ratio > a.max_ratio).sum()}) -> {a.out}")
