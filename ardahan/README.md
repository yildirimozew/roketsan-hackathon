# ardahan

Tools for scoring any model the competition's way, and YOLO11 baselines trained on Kaggle (2x T4).

## Scoring tools (usable by everyone)

| Script | What it does |
|---|---|
| `evaluate.py` | Competition metric: mAP@0.5, mean of the four per-class APs, pycocotools with `areaRng [[200, 1e10]]` (unmatched predictions under 200 px² are ignored, as the competition does) and `maxDets 1000`. Takes `image_id,label,conf,x,y,w,h` CSVs or a `submission.csv`. `--self-test` checks the edge cases. |
| `check_submission.py` | Validates a submission against `data/sample_submission.csv`: rows, image_ids and order, `none` for empty, groups of `label conf x y w h`, 0 ≤ conf ≤ 1, w and h > 0. |
| `to_yolo.py` | `annotations.csv` → YOLO labels plus list files for the five committed folds. |
| `eda.py` | Image sizes, box areas per class (near the 200 px² floor), boxes per image. |
| `grouping_check.py` | Pixel similarity between images: consecutive IDs (shuffled, no signal) and nearest neighbours (same-scene frames across the random folds). |
| `coco_zeroshot.py` | Pipeline check: COCO yolo11m with no training on fold 1 (0.287, no van class). |

```
python ardahan/evaluate.py PREDS.csv --images splits/scene_holdout_v1/val.txt
python ardahan/check_submission.py submission.csv
```

Ultralytics' own validation mAP reads high: on the nano run it said 0.685 where `evaluate.py` gives 0.656.
Decide with `evaluate.py`.

## Kaggle runs (`kaggle/`)

Both train on fold 1 of `splits/folds/` (random split, made before `scene_holdout_v1` existed), so they can only be
scored on `fold_1_val.txt`: 1,054 of the 1,295 `scene_holdout_v1` validation images are in their training data.

| Run | Config | Result on fold 1 (`evaluate.py`) |
|---|---|---|
| `yolo11n_fast` | yolo11n, COCO init, imgsz 1280, 35 epochs, batch 16 (8 per T4), fliplr/flipud 0.5, scale 0.4, mosaic, close_mosaic 10, cos_lr | **0.656** (car 0.857, van 0.535, truck 0.558, bus 0.676); 151 s/epoch, 1.47 h |
| `yolo11m_baseline` | same with yolo11m, batch 8 (4 per T4: 8 per T4 runs out of memory at 1280) | running; 329 s/epoch, 3.2 h |

Kaggle notes:
- The kernels run offline: ultralytics wheels, COCO weights and `yolo26n.pt` (Ultralytics' AMP check) come from a
  private deps dataset. A missing `yolo26n.pt` costs ~96 s of timeouts before AMP proceeds anyway.
- The dataset is copied to `/kaggle/working` first (reading `/kaggle/input` ran at ~40 MB/s).
- Predictions use `last.pt`, conf 0.001, max_det 1000, one image at a time (a list of paths is one batch in
  Ultralytics and runs out of memory). Boxes clipped at the image edge to zero width or height are dropped.
- `kaggle kernels logs` returns nothing while a kernel runs; `kaggle/live_log.py OWNER/KERNEL` reads the live stream.
