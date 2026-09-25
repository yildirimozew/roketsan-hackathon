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

Karolina currently records W&B runs in offline mode because the configured API
credential has read but not write access to the project. After fixing project
permissions, sync every framework's run with `find /mnt/proj1/open-37-16/yildirimozew/eli-training/runs -type d -name 'offline-run-*' -exec wandb sync {} +`.

## RF-DETR scene-holdout A/B

`submit_rfdetr_ab.sh` prepares a separate `scene_holdout_v1` RF-DETR dataset,
then submits matched three-epoch A/B jobs to `qgpu_exp`. Both arms use the same
704px grid and rare-class-centered crops; arm B alone enables mild normalized
class weights. Dependent evaluation jobs reconstruct the original validation
images and report the competition's all-point mAP@0.5 at the fixed owner-only,
class-wise NMS 0.60 configuration.
