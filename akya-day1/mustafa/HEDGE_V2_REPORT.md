# HEDGE v2 REPORT — FAKE DATA ONLY (no real val predictions yet)

`mustafa/preds/` contains **no real validation prediction CSV** (only `fake_val*`). Every number below comes from synthetic preds made by `mustafa/make_fake_val.py`: GT from `scene_holdout_v2/val.txt` with 10% dropped, ±5% jitter, 15% car→van, 25% van→car and 15% truck→bus relabels, and 3 random false positives per image.
The fake set injects confusion but has **none of the "flooding" risk**. It has no real low-confidence vans for copied cars to outrank. So it cannot show a direction hurting its target class, and larger alphas always look better here.

## Tools
- `hedge_classes_v2.py`: per-direction alphas (`--car2van --van2car --truck2bus --bus2truck`, 0 = off), `--min-conf` (default 0.05), `--dedup-iou` (default 0.7, `<=0` = off), `--probs` (copy conf = conf × p(target)), `--config JSON`, and max 1000 boxes per image. Input and output are a prediction CSV or a submission, same format out. Reuses v1 I/O; v1 is unchanged.
- `sweep_hedge_v2.py`: scores in-process via `score_hedge.load_context/score`. `score_hedge.py` was refactored to be importable; its CLI output is unchanged. It writes the best config JSON and a markdown table file `<preds>_sweep_v2.md`.

## Fake results (`fake_val.csv`, 1295 images)

Each direction was run alone, with min_conf 0.05 and dedup_iou 0.7:

| direction (target) | α=0.05 | 0.1 | 0.2 | 0.3 | 0.5 | ΔmAP at chosen α | chosen α |
|---|---|---|---|---|---|---|---|
| car2van (van AP, base 0.5405) | 0.5814 | 0.5815 | 0.5818 | 0.5822 | 0.5830 | +0.0106 | 0.5 |
| van2car (car AP, base 0.7488) | 0.8613 | 0.8615 | 0.8624 | 0.8632 | 0.8649 | +0.0290 | 0.5 |
| truck2bus (bus AP, base 0.8560) | 0.8560 | 0.8560 | 0.8560 | 0.8560 | 0.8560 | +0.0000 | **0 (off)** |
| bus2truck (truck AP, base 0.7624) | 0.8285 | 0.8291 | 0.8317 | 0.8347 | 0.8423 | +0.0200 | 0.5 |

truck2bus has no effect because the fake set contains no bus→truck mistakes for it to fix.

Combined chosen alphas across min_conf {0, 0.05, 0.1} × dedup {0.5, 0.7, off}: every setting falls within 0.7865–0.7866 mAP. Dedup 0.5 costs about 0.0005 test-weighted, and min_conf makes no difference.

| setting | mAP@0.5 | test-weighted | car | van | truck | bus |
|---|---|---|---|---|---|---|
| no hedge | 0.7269 | 0.7315 | 0.7488 | 0.5405 | 0.7624 | 0.8560 |
| best combined | **0.7866** | **0.7907** | 0.8649 | 0.5830 | 0.8424 | 0.8560 |
| Δ | +0.0596 | +0.0592 | +0.1161 | +0.0425 | +0.0800 | 0 |

Fake config, saved to `mustafa/preds/hedge_v2_best_fake.json` (git-ignored; **do not apply to a real submission**):
```json
{"car2van": 0.5, "van2car": 0.5, "truck2bus": 0.0, "bus2truck": 0.5, "min_conf": 0.0, "dedup_iou": null}
```

## Real results
**None yet.** No real val CSV has been found, so `mustafa/hedge_v2_best.json` has not been created. When one arrives, e.g. `furkan_y11m_v2_val_preds.csv` or `ens0834_val.csv`:
```bash
python mustafa/sweep_hedge_v2.py mustafa/preds/<real>_val.csv          # -> mustafa/hedge_v2_best.json + preds/<real>_val_sweep_v2.md
```

## Recommendation
The mechanism works: each direction can be switched on or off, dedup and min-conf work, and a direction that doesn't help its target class is dropped (truck2bus here). The alpha values themselves are meaningless on fake data. On real predictions, expect car2van and truck2bus to need small alphas or to be switched off because of flooding. Choose the settings **only** from a real sweep on `scene_holdout_v2`.

## Applying the chosen config to a test submission (after a real sweep)
```bash
python mustafa/hedge_classes_v2.py --inp <test_submission>.csv --out mustafa/preds/<test_submission>_hedged.csv --config mustafa/hedge_v2_best.json
python ardahan/check_submission.py mustafa/preds/<test_submission>_hedged.csv
```

## Files to commit
- `mustafa/hedge_classes_v2.py`
- `mustafa/sweep_hedge_v2.py`
- `mustafa/score_hedge.py` (refactored)
- `mustafa/HEDGE_V2_REPORT.md`
- Also if not yet committed: `mustafa/.gitignore`, `mustafa/hedge_classes.py`, `mustafa/make_fake_val.py`, `mustafa/HEDGE_REPORT.md`, `mustafa/docs/CONTEXT.md`, `mustafa/tests/test_hedge.py`
- Commit `mustafa/hedge_v2_best.json` only after a real sweep.
