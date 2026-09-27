# HEDGE_REPORT — FAKE DATA (mechanism test, not a real model)

No real validation predictions exist in `mustafa/preds/`. All numbers below come from **synthetic predictions** built from ground truth (`mustafa/make_fake_val.py`, seed 42). They show how the hedging mechanism behaves under injected class confusion; they say nothing about a real model.

## 1. Inventory of `mustafa/`

| Item | What it is | State |
|---|---|---|
| `.gitignore` | ignores `debug/`, `preds/`, `local/`, `_*_out.txt`, `_explore_*.txt` | complete, untracked |
| `.gitkeep` | placeholder | tracked |
| `hedge_classes.py` | car↔van / truck↔bus class hedging, preds or submission CSV, `--alpha`/`--sweep` | complete, untracked |
| `make_fake_val.py` | synthetic val preds from GT (this run) | complete, new |
| `score_hedge.py` | scores CSVs with `ardahan/evaluate.py` and test-weighted mAP | complete, new |
| `HEDGE_REPORT.md` | this report | complete |
| `_check_boxes_out.txt`, `_explore_*.txt`, `_prepare_yolo_out.txt` | logs from earlier exploration runs | git-ignored |
| `debug/` | 6 files (coordinate/YOLO check images, `coord_verdict.txt`) | git-ignored |
| `preds/` | 5 CSVs (`fake_val.csv` + 4 hedged) | git-ignored |
| `local/` | does not exist | — |
| `DATA_REPORT.md`, `prepare_yolo.py`, `data_local.yaml`, `make_pseudo_labels.py` | **missing** (only their logs remain; the team YOLO prep script is `furkan/src/prepare_yolo.py`) | — |

`git status --short mustafa/` at start: `?? .gitignore`, `?? HEDGE_REPORT.md`, `?? hedge_classes.py`.
`collective_summary.txt` has no lines about Mustafa. What matters for this task: the recommended split is now **`splits/scene_holdout_v2`** (furkan; README still names v1), and scores should be test-weighted with `splits/scene_holdout_v2/val_strata.csv`.

## 2. Metric

`python ardahan/evaluate.py PREDS --images MANIFEST [--annotations data/train/annotations.csv]` accepts a preds CSV or a Kaggle submission. It computes the competition mAP@0.5 with pycocotools: IoU 0.5, mean of the car/van/truck/bus APs, maxDets 1000, and unmatched predictions under 200 px² ignored. It prints the overall mAP and each class AP. It has **no test-weighted mode**. So `score_hedge.py` adds one: an image-weighted AP@0.5 using the `val_strata.csv` weights, with the same logic as `yildirim/one_hour_models/evaluate_yolo_sliced.weighted_map`. `check_submission.py` only checks the submission format.

## 3. Results (fake preds, `scene_holdout_v2/val.txt`, 1295 images)

Fake preds: boxes jittered ±5%, conf 0.5–1.0; 10% dropped; 15% car→van, 25% van→car, 15% truck→bus relabelled with conf 0.4–0.8; 3 random false boxes per image with conf 0.05–0.4.

| alpha | mAP@0.5 | car | van | truck | bus | test-weighted |
|---|---|---|---|---|---|---|
| no hedge | 0.7269 | 0.7488 | 0.5405 | 0.7624 | 0.8560 | 0.7315 |
| 0.10 | 0.7820 | 0.8615 | 0.5815 | 0.8291 | 0.8560 | 0.7861 |
| 0.20 | 0.7830 | 0.8624 | 0.5818 | 0.8317 | 0.8560 | 0.7871 |
| 0.30 | 0.7841 | 0.8632 | 0.5822 | 0.8348 | 0.8560 | 0.7882 |
| **0.50** | **0.7866** | **0.8649** | **0.5830** | **0.8424** | 0.8560 | **0.7907** |

**Best alpha: 0.50**, +0.060 mAP@0.5 and +0.059 test-weighted over no hedge.
- Gains: car +0.116, van +0.043, truck +0.080.
- Bus: unchanged. No bus→truck confusion was injected, and the extra low-confidence bus copies of trucks rank below the true buses. There were no per-class losses.
- The choice of alpha matters much less than hedging itself: 0.1 to 0.5 moves the score by only 0.005.

**Recommendation:** Hedging is essentially free insurance when classes get confused, but these numbers are synthetic. Run `hedge_classes.py --sweep` and `score_hedge.py` on a real model's `scene_holdout_v2` val predictions before using it in a submission.

Reproduce:
```
python mustafa/make_fake_val.py
python mustafa/hedge_classes.py --inp mustafa/preds/fake_val.csv --sweep
python mustafa/score_hedge.py mustafa/preds/fake_val.csv mustafa/preds/fake_val_hedge0.*.csv
```

## Files to commit

- `mustafa/.gitignore`
- `mustafa/hedge_classes.py`
- `mustafa/make_fake_val.py`
- `mustafa/score_hedge.py`
- `mustafa/HEDGE_REPORT.md`
