#!/bin/bash
#SBATCH --job-name=eli-yolo-cv-embed
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=00:10:00

set -euo pipefail
module purge
module load Python/3.12.3-GCCcore-13.3.0

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
FULL_RUN="$ELI_ROOT/runs/yolo_scene_full_v2"
OUTPUT="$FULL_RUN/convnext_embedding/features"
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export OMP_NUM_THREADS=8

test ! -e "$OUTPUT"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/yolo_convnext_embedding.py" extract \
    --raw "$FULL_RUN/evaluation/raw_tile_predictions.npz" \
    --annotations "$ELI_ROOT/prepared/yolo_scene_pilots/validation/images/val/_annotations.coco.json" \
    --images "$REMOTE_REPO/data/train/images" \
    --classifier "$ELI_ROOT/runs/convnext_cv_v2/best_ema.pt" \
    --output "$OUTPUT" \
    --nms-iou 0.60 \
    --batch-size 512
