# One-hour architecture pilots

Five independent A100 pilots using `splits/folds/fold_1_{train,val}.txt`:

1. YOLO26-S-P2 at 1280 px
2. YOLO12-L at 1280 px
3. RF-DETR Large on overlapping 704 px tiles
4. D-FINE-L at 960 px
5. Cascade R-CNN ConvNeXt-T/FPN

`prepare_data.py` creates YOLO, COCO, and tiled COCO datasets without copying
the full-resolution source images. Generated datasets, environments,
checkpoints, and logs are intentionally ignored by Git.

On Karolina, `submit_all.sh` submits a CPU preparation job followed by five
one-GPU jobs named `eli-training-1` through `eli-training-5`. Each training
process gets 3,600 seconds; validation and environment setup are outside that
budget. Training and validation metrics are logged to the W&B project
`eli-training`, with one run named after each Slurm job.

Karolina compute jobs always capture W&B data offline because compute-node
network access is unreliable. The login-node credential has verified write
access to `yildirimozew-eth-z-rich/eli-training`. After jobs finish, run
`bash yildirim/one_hour_models/sync_wandb_karolina.sh` from the repository on a
Karolina login node. The helper loads the correct Python module, verifies the
credential, skips active and already-synced runs, and uploads the remainder.

## RF-DETR scene-holdout A/B

`submit_rfdetr_ab.sh` prepares a separate `scene_holdout_v1` RF-DETR dataset,
then submits matched three-epoch A/B jobs to `qgpu_exp`. Both arms use the same
704px grid and rare-class-centered crops; arm B alone enables mild normalized
class weights. Dependent evaluation jobs reconstruct the original validation
images and report the competition's all-point mAP@0.5 at the fixed owner-only,
class-wise NMS 0.60 configuration.

`submit_rfdetr_a_long.sh` resumes arm A from its full epoch-3 checkpoint and
trains to epoch 15 through four dependent `qgpu_exp` jobs. It then evaluates
the best EMA checkpoint and writes full tiled test predictions and a submission CSV.

## ConvNeXt car/van reclassifier

`submit_convnext_cv.sh` builds leakage-safe car/van crops from
`scene_holdout_v1`, fine-tunes ImageNet ConvNeXt-Tiny, extracts aligned RF-DETR
query logits from the long-run best EMA checkpoint, and fits scene-grouped OOF
logit fusion. Test-time relabeling is enabled only when OOF competition mAP
improves by at least 0.005; otherwise the pipeline emits the detector-only
fallback. GPU allocations total 40 minutes and all outputs use separate paths.

## YOLO26 sliced-data pilots

`submit_yolo_sliced_pilots.sh` prepares deterministic 704px sliced datasets from
`scene_holdout_v2`, then runs three YOLO26-S-P2 pilots. Pilots 1 and 2 compare
AdamW learning rates `1e-3` and `5e-4` on the same 25% rare-class-centered data.
The better learning rate, subject to a 0.005 weighted-mAP improvement threshold,
feeds pilot 3 on 40% centered data. Evaluation uses owner-filtered full-grid
inference on original validation images, the exact competition mAP@0.5, and the
test-stratum-weighted score. All W&B runs are captured offline for later sync.
