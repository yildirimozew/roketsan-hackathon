#!/bin/bash
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=00:59:00

set -euo pipefail

: "${PREPARED:?PREPARED must be set}"
: "${WEIGHTS:?WEIGHTS must be set}"
: "${RUN_DIR:?RUN_DIR must be set}"

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon/akya-day1
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
RUN_NAME="${RUN_NAME:-yolo26-full-v2-finetune}"
EPOCHS="${EPOCHS:-3}"

module purge
module load Python/3.12.3-GCCcore-13.3.0
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export YOLO_CONFIG_DIR="$ELI_ROOT/runs/yolo-config"
export OMP_NUM_THREADS=8
source "$SOURCE_DIR/wandb_karolina.env"
export WANDB_RUN_GROUP="${WANDB_RUN_GROUP:-yolo26-full-v2-finetune}"
export WANDB_DIR="$ELI_ROOT/runs/wandb/$RUN_NAME"
export ELI_GIT_COMMIT="${ELI_GIT_COMMIT:-unknown}"
mkdir -p "$WANDB_DIR"

"$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/check_yolo_sliced.py" \
    --prepared "$PREPARED" --repo "$REMOTE_REPO"

"$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/finetune_yolo_full.py" \
    --data "$PREPARED/dataset_ratio25.yaml" \
    --weights "$WEIGHTS" \
    --output "$RUN_DIR" \
    --epochs "$EPOCHS" \
    --workers 12 \
    --wandb-project eli-training \
    --wandb-run "$RUN_NAME" \
    --wandb-group "$WANDB_RUN_GROUP"
