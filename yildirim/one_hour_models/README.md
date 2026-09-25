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
