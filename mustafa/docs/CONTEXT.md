# Context: class-hedging test

## Done
- `mustafa/hedge_classes.py`: adds a copy of every box with the paired class (car↔van, truck↔bus) at conf × alpha. `--sweep` tries alpha 0.1/0.2/0.3/0.5.
- `mustafa/score_hedge.py`: mAP@0.5 via `ardahan/evaluate.py` plus test-weighted mAP (weights from `splits/scene_holdout_v2/val_strata.csv`).
- Tested only on fake preds (`mustafa/make_fake_val.py`): alpha 0.5 gave +0.06 mAP. See `mustafa/HEDGE_REPORT.md`.

## Blocked
Waiting for teammates to provide real `scene_holdout_v2` val predictions (from Kaggle runs) as `mustafa/preds/real_val.csv`.
Accepted formats: `image_id,label,conf,x,y,w,h` or a Kaggle submission (`image_id,PredictionString`).

## Run once the CSV arrives
```bash
python mustafa/hedge_classes.py --inp mustafa/preds/real_val.csv --sweep
python mustafa/score_hedge.py mustafa/preds/real_val.csv mustafa/preds/real_val_hedge0.*.csv
```
