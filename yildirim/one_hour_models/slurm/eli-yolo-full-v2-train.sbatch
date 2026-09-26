#!/bin/bash
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=04:30:00

set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
PREPARED="$ELI_ROOT/prepared/yolo_scene_pilots"
PILOT_DIR="$ELI_ROOT/runs/yolo_scene_pilots/pilot2"
RUN_DIR="$ELI_ROOT/runs/yolo_scene_full_v2"
RUN_NAME=yolo26-sliced-full-v2-train

module purge
module load Python/3.12.3-GCCcore-13.3.0
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export YOLO_CONFIG_DIR="$ELI_ROOT/runs/yolo-config"
export OMP_NUM_THREADS=8
source "$SOURCE_DIR/wandb_karolina.env"
export WANDB_RUN_GROUP=yolo26-sliced-full-v2
export WANDB_DIR="$ELI_ROOT/runs/wandb/$RUN_NAME"
export ELI_GIT_COMMIT="${ELI_GIT_COMMIT:-unknown}"
mkdir -p "$WANDB_DIR" "$RUN_DIR"

"$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/check_yolo_sliced.py" \
    --prepared "$PREPARED" --repo "$REMOTE_REPO"

"$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/train_yolo_full.py" \
    --data "$PREPARED/dataset_ratio25.yaml" \
    --checkpoint "$PILOT_DIR/train/weights/epoch8.pt" \
    --initial-best "$PILOT_DIR/train/weights/best.pt" \
    --output "$RUN_DIR" \
    --patience 6 \
    --workers 12 \
    --wandb-project eli-training \
    --wandb-run "$RUN_NAME" \
    --wandb-group yolo26-sliced-full-v2
