#!/bin/bash
#SBATCH --job-name=eli-cv-calibrate
#SBATCH --account=open-37-16
#SBATCH --partition=qcpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=01:00:00

set -euo pipefail
module purge
module load Python/3.12.3-GCCcore-13.3.0

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
RUN_DIR="$ELI_ROOT/runs/rfdetr_convnext_cv"
export WANDB_RUN_GROUP=rfdetr-convnext-cv
export WANDB_NAME=rfdetr-convnext-cv-calibration
export WANDB_DIR="$ELI_ROOT/runs/wandb/rfdetr-convnext-cv-calibration"
source "$SOURCE_DIR/wandb_karolina.env"
mkdir -p "$WANDB_DIR"

test ! -e "$RUN_DIR/calibration"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/rfdetr_convnext_fusion.py" calibrate \
    --features "$RUN_DIR/validation_features" \
    --annotations "$ELI_ROOT/prepared/rfdetr_scene_ab/coco/valid/_annotations.coco.json" \
    --groups "$REMOTE_REPO/splits/scene_holdout_v1/groups.csv" \
    --output "$RUN_DIR/calibration"
