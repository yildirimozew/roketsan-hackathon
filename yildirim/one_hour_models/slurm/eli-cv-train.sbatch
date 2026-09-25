#!/bin/bash
#SBATCH --job-name=eli-cv-train
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=00:20:00

set -euo pipefail
module purge
module load Python/3.12.3-GCCcore-13.3.0

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
RUN_DIR="$ELI_ROOT/runs/convnext_cv"
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export WANDB_RUN_GROUP=rfdetr-convnext-cv
export WANDB_NAME=convnext-cv-train
export WANDB_DIR="$ELI_ROOT/runs/wandb/convnext-cv-train"
source "$SOURCE_DIR/wandb_karolina.env"
mkdir -p "$WANDB_DIR"

test ! -e "$RUN_DIR"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/train_convnext_cv.py" \
    --data "$ELI_ROOT/prepared/convnext_cv" \
    --weights "$ELI_ROOT/weights/convnext_tiny-983f1562.pth" \
    --output "$RUN_DIR" \
    --epochs 4 \
    --batch-size 256 \
    --seed 42
