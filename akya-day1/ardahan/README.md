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

Each folder holds the kernel (`train.py`, `kernel-metadata.json`) and, for runs that finished, Ultralytics'
`args.yaml` and per-epoch `results.csv`. Weights and predictions stay out of git (`outputs/kaggle_<run>/`).
Every run: COCO init, imgsz 1280, 2x T4 with DDP, batch 8 (4 per T4; 8 per T4 runs out of memory at 1280),
fliplr and flipud 0.5, degrees 0, scale 0.4, mosaic 1.0, cos_lr, AMP. Scores are `evaluate.py` on `last.pt`.

### Fold 1 (random split, before `scene_holdout_v1` existed)

1,054 of the 1,295 `scene_holdout_v1` validation images are in their training data, so they can only be scored on
`splits/folds/fold_1_val.txt`.

| Run | Config | fold-1 val mAP@0.5 |
|---|---|---|
| `yolo11n_fast` | yolo11n, 35 epochs, batch 16 (8 per T4), close_mosaic 10; 151 s/epoch | 0.6563 (car 0.857, van 0.535, truck 0.558, bus 0.676) |
| `yolo11m_baseline` | yolo11m, 35 epochs, close_mosaic 10; 329 s/epoch | 0.7511 (car 0.900, van 0.631, truck 0.684, bus 0.790) |

### scene_holdout_v2

Trained on `splits/scene_holdout_v2/train.txt`, scored on its `val.txt` (1,295 images).

| Run | Config | Epochs | val mAP@0.5 | car | van | truck | bus |
|---|---|---|---|---|---|---|---|
| `yolo11m_sh2` | yolo11m, no resampling, close_mosaic 10 | 35 | 0.7544 | 0.896 | 0.619 | 0.708 | 0.794 |
| `yolo11m_sh2_rfs` | + repeat-factor sampling (below); cut to 18 epochs by the 3.5 h budget, which matches `yolo11m_sh2`'s compute | 18 | 0.7671 | 0.896 | 0.629 | 0.729 | 0.815 |
| `yolo11m_sh2_rfs_e30` | same recipe, cosine schedule planned for 30 epochs | 30 | **0.7772** | 0.899 | 0.644 | 0.740 | 0.826 |
| `yolo11m_sh2_rfs_e40` | same recipe, 40 epochs | | no outputs downloaded | | | | |
| `yolo11l_sh2` | yolo11l, no resampling | 42 | 0.7467 | 0.895 | 0.585 | 0.715 | 0.791 |

**Repeat-factor sampling.** Buses are 3% of boxes and trucks 7%, but each class is a quarter of mAP. Images are
listed several times in the training list (Ultralytics keeps duplicates): an image with a bus x3, a truck but no
bus x2, anything else x1. That gives 9,986 entries per epoch instead of 5,176 (1.93x); `warmup_epochs` (1.55) and
`close_mosaic` (5) are divided by 1.93 to keep the same number of iterations. It lifts every rare class, and van too.

**Why `last.pt`.** `best.pt` is picked by Ultralytics' own mAP on the validation set we score on, so it reads high.

## Test-time augmentation and fusion

| Script | What it does |
|---|---|
| `predict_yolo.py` | Predict a manifest of train or test images with any YOLO checkpoint: `--imgsz`, `--hflip`, `--augment`. |
| `tta_eval.py` | Scores single views and WBF fusions of views for one model on v2 val. |
| `tta_merge.py` | Merges one model's four views (plain and hflip at 1280 and 1536) into one CSV per split. |
| `tta_combos.py` | Views x models x WBF settings on v2 val, to pick the input to the crop classifier. |
| `fuse_wbf.py` | WBF (`ensemble_boxes`) of YOLO11m and RF-DETR Large on fold 1. |
| `crop_classifier.py` | Car/van/truck/bus crop classifier (timm `convnext_tiny.in12k_ft_in1k`, 128 px crops) that rescores fused boxes. |

4-view TTA (plain + hflip, 1280 + 1536, fused by WBF) is worth about +0.04 on every YOLO11m:

| Model | plain | 4-view TTA |
|---|---|---|
| `yolo11m_sh2` | 0.7544 | 0.7985 |
| `yolo11m_sh2_rfs` | 0.7671 | 0.8087 |
| `yolo11m_sh2_rfs_e30` | 0.7772 | 0.8172 |

### Final YOLO ensemble: 0.8416 on v2 val

`outputs/ensemble_final/` (README, code, weights, training logs; not in git). 13 inputs, equal weights, WBF at IoU
0.7 (`conf_type avg`, top 1000 per image):

- the 4 TTA views of `yolo11m_sh2`, `yolo11m_sh2_rfs` and `yolo11m_sh2_rfs_e30` (12 views);
- `yolo11l_sh2`, plain 1280.

Then the crop classifier rescores every box: with t the sum of its class scores and q the classifier's
probabilities, the new score for class c is t((1 - w) s_c / t + w q_c), at w 0.35. That gives 0.8416 mAP@0.5 (0.8373
weighted to the test set's resolution x brightness mix).

Settings, all chosen on v2 val split into two scene-group halves:
- WBF IoU 0.7: swept 0.55 / 0.6 / 0.7 / 0.75 / 0.8; best on both halves.
- Inputs: 12 views + yolo11l beat 12 views, 8 views without rfs-18, and 10 views with Ultralytics `--augment`.
- Rescoring weight w: the halves picked 0.3 and 0.4, and the gain is flat between them.
- Duplicating car boxes as van after rescoring lowered mAP at every setting tried (0.2-0.5), so it's off.

`yolo11m_sh2_rfs_e30`'s plain test predictions are also one of the four inputs to the team's final 4-model
ensemble (see [`roketsan_ensemble.ipynb`](../roketsan_ensemble.ipynb)).

## Analysis

| Script | What it does |
|---|---|
| `confusion.py` | Detection confusion matrix: are errors misclassifications or missed boxes? |
| `embed_images.py` | DINOv2-small embeddings of every train and test image. |
| `leakage_check.py` | Near-duplicate images across splits from those embeddings; writes scene-grouped folds to `splits/grouped_dinov2/`. |
| `leakage_map.py` | How much near-duplicate leakage inflates fold-1 mAP; also used by `evaluate.py --weights`. |
| `crop_embeddings.py` | DINOv2 embeddings of box crops per class, with a validity gate. |

`evaluate.py --weights splits/scene_holdout_v2/val_strata.csv` also reports mAP reweighted to the test set's
resolution x brightness mix, and mAP per stratum. `image_sizes_{train,test}.csv` cache image sizes for the scripts.

Kaggle notes:
- The kernels run offline: ultralytics wheels, COCO weights and `yolo26n.pt` (Ultralytics' AMP check) come from a
  private deps dataset. A missing `yolo26n.pt` costs ~96 s of timeouts before AMP proceeds anyway.
- The dataset is copied to `/kaggle/working` first (reading `/kaggle/input` ran at ~40 MB/s).
- Predictions use `last.pt`, conf 0.001, max_det 1000, one image at a time (a list of paths is one batch in
  Ultralytics and runs out of memory). Boxes clipped at the image edge to zero width or height are dropped.
- `kaggle kernels logs` returns nothing while a kernel runs; `kaggle/live_log.py OWNER/KERNEL` reads the live stream.
