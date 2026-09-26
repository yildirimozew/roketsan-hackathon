# Context: class hedging + submission

## Done
- `hedge_classes.py` (v1): adds a copy of every box with the paired class (car↔van, truck↔bus) at conf × alpha.
- `hedge_classes_v2.py`: alpha per direction, min-conf, IoU dedup, `--config JSON`. `sweep_hedge_v2.py` picks the settings and writes `mustafa/hedge_v2_best.json`.
- `score_hedge.py`: mAP@0.5 via `ardahan/evaluate.py` plus test-weighted mAP (`splits/scene_holdout_v2/val_strata.csv`).
- `format_submission.py`: prediction CSV → Kaggle `image_id,PredictionString` in sample order, "none" for empty images, then runs `ardahan/check_submission.py`.
- `optimize_conf.py`: scores min-conf cuts 0.05–0.50 on a val CSV. AP can only fall when boxes are cut, so use it to check what a cut costs (e.g. for file size), not to gain mAP. By default, don't cut.
- `class_thresholds.py`: drops boxes with conf ≤ a per-class threshold (defaults car/truck 0.30, van/bus 0.15; `--car --van --truck --bus`). Like `optimize_conf.py`, it can only lower mAP: use it only if the file must shrink, and score it with `score_hedge.py` on val first.
- `filter_area.py`: drops boxes with w/h ≤ 0 or area outside [100, 500000] px² (`--min-area --max-area`). Train GT spans 200–328,640 px², so the defaults remove no real vehicle, and the metric already ignores unmatched boxes < 200 px². It is a safe sanity step before `format_submission.py`.
- `filter_ratio.py`: drops boxes with w/h outside [0.1, 15] (`--min-ratio --max-ratio`). Train GT spans 0.164–12.54, and 99 real boxes fall outside 0.2–5 (cut-off cars/trucks), so don't tighten it to 0.2–5.
- Tested only on fake preds so far (see `HEDGE_REPORT.md`, `HEDGE_V2_REPORT.md`).

## Blocked
Waiting for teammates to provide real `scene_holdout_v2` val predictions as `mustafa/preds/real_val.csv` (`image_id,label,conf,x,y,w,h` or a submission).

## Final pipeline
```bash
# 1. choose hedge settings on val
python mustafa/sweep_hedge_v2.py mustafa/preds/real_val.csv            # -> mustafa/hedge_v2_best.json
#    optional: see what a confidence cut would cost
python mustafa/optimize_conf.py mustafa/preds/real_val.csv
# 2. hedge the test predictions with those settings
python mustafa/hedge_classes_v2.py --inp mustafa/preds/test_preds.csv --out mustafa/preds/test_preds_hedged.csv --config mustafa/hedge_v2_best.json
# 3. drop boxes with impossible sizes
python mustafa/filter_area.py --inp mustafa/preds/test_preds_hedged.csv --out mustafa/preds/test_preds_clean.csv
python mustafa/filter_ratio.py --inp mustafa/preds/test_preds_clean.csv --out mustafa/preds/test_preds_clean.csv
# 4. convert to the Kaggle format and validate (prints OK / FAILED)
python mustafa/format_submission.py --inp mustafa/preds/test_preds_clean.csv --out mustafa/preds/submission.csv
```
If the sweep keeps no direction (all alphas 0), skip step 2 and format `test_preds.csv` directly.
