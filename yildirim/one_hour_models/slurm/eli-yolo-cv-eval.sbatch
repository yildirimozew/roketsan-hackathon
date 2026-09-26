#!/bin/bash
#SBATCH --job-name=eli-yolo-cv-eval
#SBATCH --account=open-37-16
#SBATCH --partition=qcpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=00:40:00

set -euo pipefail
module purge
module load Python/3.12.3-GCCcore-13.3.0

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
FULL_RUN="$ELI_ROOT/runs/yolo_scene_full_v2"
OUTPUT="$FULL_RUN/convnext_embedding/evaluation"
export WANDB_RUN_GROUP=yolo26-convnext-v2
export WANDB_NAME=yolo26-convnext-v2-eval
export WANDB_DIR="$ELI_ROOT/runs/wandb/yolo26-convnext-v2-eval"
source "$SOURCE_DIR/wandb_karolina.env"
mkdir -p "$WANDB_DIR"

test ! -e "$OUTPUT"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/yolo_convnext_embedding.py" evaluate \
    --features "$FULL_RUN/convnext_embedding/features" \
    --annotations-csv "$REMOTE_REPO/data/train/annotations.csv" \
    --groups "$REMOTE_REPO/splits/scene_holdout_v2/groups.csv" \
    --weights "$REMOTE_REPO/splits/scene_holdout_v2/val_strata.csv" \
    --baseline-metrics "$FULL_RUN/evaluation/merged_metrics.json" \
    --repo "$REMOTE_REPO" \
    --output "$OUTPUT"
