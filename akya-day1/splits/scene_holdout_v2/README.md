# Scene holdout v2

Fixed 5,176 / 1,295 train/validation split. Use `val.txt` for validation only.
Built by `furkan/src/make_scene_holdout_v2.py` (seed 42); `metadata.json` holds the full audit.

## Why v2

v1 matched the test resolution mix but also forced the global class mix to equal train's. The two
goals conflict, so the optimiser filled 1400x788 (44% of test) with low-bus, mostly bright scenes.
v2 matches the test distribution per resolution x brightness stratum and, inside each stratum,
the labelled pool's class mix. The global class mix is whatever that implies (bus rises).

## Method

1. **Groups.** v1's 4,891 scene groups (ResNet-18 cosine >= 0.90, same resolution, connected
   components) are reused unchanged; each group is wholly train or validation.
2. **Brightness.** 64x64 grayscale mean; dark = brightness < 55, as in v1 (dark counts reproduce v1's).
3. **Strata.** native resolution x {dark, light}. Target T_s = 1295 * p_test(s) from unlabeled test
   images; strata absent from test get 0 validation images. No stratum may give more than
   50% of its labelled images to validation, so train keeps every test domain; a capped
   stratum's excess target goes to the other test strata in proportion to p_test.
   Capped: 1360x765_light (test target 334, pool 729, val 363), 1400x788_dark (test target 232, pool 224, val 112).
4. **Selection.** Binary MILP over groups (pulp + CBC, 120 s): exactly 1,295 images,
   |val_s - T_s| <= max(3, ceil(0.03 * T_s)) and val_s <= cap_s, minimising the normalised deviation from
   pool_sf * T_s / N_s for per-class boxes, per-class presence, background, density bins and
   median-box-area quartile bins. No global class-share constraint.
5. **Audit.** Zero group crossings, exact image partition, every stratum within tolerance,
   exact-duplicate images on one side; dHash near-duplicates reported for information only.

## v1 / v2 / test

| | v1 val | v2 val | v2 val weighted | v2 train | pool | test |
|---|---:|---:|---:|---:|---:|---:|
| share 1360x765_dark | 0.3% | 0.5% | 0.4% | 0.1% | 0.2% | 0.4% |
| share 1360x765_light | 25.9% | 28.0% | 25.8% | 7.1% | 11.3% | 25.8% |
| share 1400x1050_dark | 6.4% | 0.8% | 0.8% | 10.9% | 8.9% | 0.8% |
| share 1400x1050_light | 6.6% | 13.7% | 12.2% | 33.7% | 29.7% | 12.2% |
| share 1400x788_dark | 11.8% | 8.6% | 17.9% | 2.2% | 3.5% | 17.9% |
| share 1400x788_light | 32.2% | 29.4% | 26.1% | 13.4% | 16.6% | 26.1% |
| share 1916x1078_light | 7.1% | 8.0% | 7.1% | 8.3% | 8.3% | 7.1% |
| share 1920x1080_dark | 0.0% | 0.1% | 0.1% | 0.3% | 0.3% | 0.1% |
| share 1920x1080_light | 2.4% | 2.6% | 2.3% | 5.5% | 5.0% | 2.3% |
| share 960x540_dark | 0.9% | 0.3% | 0.2% | 0.4% | 0.4% | 0.2% |
| share 960x540_light | 6.4% | 8.0% | 7.0% | 2.4% | 3.5% | 7.0% |
| 1400x788 bus box share | 7.3% | 10.5% | 10.2% | 10.6% | 10.6% | – |
| 1400x788 dark rate | 26.8% | 22.7% | 40.7% | 13.9% | 17.2% | 40.7% |
| global car box share | 75.5% | 71.9% | 72.1% | 76.4% | 75.5% | – |
| global van box share | 13.8% | 14.7% | 14.3% | 13.6% | 13.8% | – |
| global truck box share | 7.3% | 8.4% | 8.4% | 7.1% | 7.3% | – |
| global bus box share | 3.4% | 5.1% | 5.2% | 3.0% | 3.4% | – |
| mean brightness | 91.7 | 99.9 | 93.2 | 94.6 | 95.7 | 91.9 |

"v2 val weighted" applies the `val_strata.csv` weights. `val_strata.csv` gives each validation
image's stratum flags and an importance weight p_test(s) / p_val(s) (mean 1): about 2 for the capped
1400x788_dark stratum and about 0.9 elsewhere. Report the weighted score, or per-stratum scores, next to
plain mAP, because unweighted v2 validation under-represents dark 1400x788 (8.6% vs 17.9% of test).
`groups.csv` extends v1's file with `stratum`, `is_dark`, `brightness`, `split_v2`
(its `split` column is v1's assignment).

Assumption: the test set's class mix inside each stratum equals the labelled pool's; this cannot be
checked without test labels.
