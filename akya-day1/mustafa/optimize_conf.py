"""Sweep a min-confidence cut (0.05..0.50) on a val prediction CSV and score each with score_hedge.py logic.

  python mustafa/optimize_conf.py mustafa/preds/real_val.csv
Note: AP never increases when low-conf boxes are removed; this shows how much each cut costs.
"""
import sys, tempfile
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_hedge import CLASSES, load_context, read_preds, score  # noqa: E402

preds, ctx = read_preds(sys.argv[1]), load_context()
rows = []
with tempfile.TemporaryDirectory() as tmp:
    for t in [0.0, *np.round(np.arange(0.05, 0.501, 0.05), 2)]:
        f = Path(tmp) / f"conf{t:.2f}.csv"
        preds[preds.conf >= t].to_csv(f, index=False)
        r = score(read_preds(f), ctx)
        rows.append((t, len(preds[preds.conf >= t]), r))
        print(f"conf>={t:.2f}: mAP {r['map']:.4f}", flush=True)

best = max(rows, key=lambda x: (x[2]["map"], x[0]))
print("\n| min conf | boxes | mAP@0.5 | test-weighted | " + " | ".join(CLASSES) + " |\n|" + "---|" * 8)
for t, n, r in rows:
    mark = " **best**" if t == best[0] else ""
    print(f"| {'none' if t == 0 else t}{mark} | {n} | {r['map']:.4f} | {r['wmap']:.4f} | " + " | ".join(f"{r[c]:.4f}" for c in CLASSES) + " |")
print(f"\nBest threshold: {'none' if best[0] == 0 else best[0]} (mAP {best[2]['map']:.4f})")
