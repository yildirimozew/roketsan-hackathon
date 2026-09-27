#!/bin/bash
#SBATCH --job-name=eli-cv-val
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
RFDETR_REPO="$ELI_ROOT/repos/rf-detr"
PATCH="$SOURCE_DIR/rfdetr_return_logits.patch"
RUN_DIR="${RUN_DIR:-$ELI_ROOT/runs/rfdetr_convnext_cv}"
CHECKPOINT="${CHECKPOINT:-$ELI_ROOT/runs/rfdetr_scene_a/checkpoint_best_ema.pth}"
OUTPUT="${OUTPUT:-$RUN_DIR/validation_features}"
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export OMP_NUM_THREADS=8

if git -C "$RFDETR_REPO" apply --reverse --check "$PATCH" >/dev/null 2>&1; then
    echo "RF-DETR return-logits patch already applied"
else
    git -C "$RFDETR_REPO" apply --check "$PATCH"
    git -C "$RFDETR_REPO" apply "$PATCH"
fi
test ! -e "$OUTPUT"
first_image=$(find "$REMOTE_REPO/data/train/images" -type f -name '*.jpg' -print -quit)
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/verify_rfdetr_return_logits.py" \
    --checkpoint "$CHECKPOINT" --image "$first_image"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/rfdetr_convnext_fusion.py" extract \
    --images "$REMOTE_REPO/data/train/images" \
    --annotations "$ELI_ROOT/prepared/rfdetr_scene_ab/coco/valid/_annotations.coco.json" \
    --checkpoint "$CHECKPOINT" \
    --classifier "$ELI_ROOT/runs/convnext_cv/best_ema.pt" \
    --output "$OUTPUT" \
    --batch-size 16 \
    --classifier-batch-size 512 \
    --nms-iou 0.60 0.70
