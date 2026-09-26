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

: "${TARGET_EPOCHS:?TARGET_EPOCHS must be set}"

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
PREPARED="$ELI_ROOT/prepared/rfdetr_full_v1"
DATA_ROOT="$PREPARED/rfdetr_tiles"
RUN_DIR="$ELI_ROOT/runs/rfdetr_full_v1_from_e12"
RUN_NAME="${RUN_NAME:-rfdetr-full-v1-from-e12-e${TARGET_EPOCHS}}"

module purge
module load Python/3.12.3-GCCcore-13.3.0
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export TORCHINDUCTOR_CACHE_DIR="$ELI_ROOT/cache/torchinductor/$RUN_NAME"
export OMP_NUM_THREADS=8
source "$SOURCE_DIR/wandb_karolina.env"
export WANDB_RUN_GROUP=rfdetr-full-v1-from-e12
export WANDB_NAME="$RUN_NAME"
export WANDB_DIR="$ELI_ROOT/runs/wandb/$RUN_NAME"
export ELI_GIT_COMMIT="${ELI_GIT_COMMIT:-unknown}"
mkdir -p "$WANDB_DIR" "$TORCHINDUCTOR_CACHE_DIR"

"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/check_rfdetr_ab.py" --prepared "$PREPARED"

checkpoint_args=()
if [[ -n "${RESUME_CHECKPOINT:-}" ]]; then
    checkpoint_args+=(--resume "$RESUME_CHECKPOINT")
elif [[ -n "${INIT_WEIGHTS:-}" ]]; then
    checkpoint_args+=(--init-weights "$INIT_WEIGHTS")
else
    echo "INIT_WEIGHTS or RESUME_CHECKPOINT must be set" >&2
    exit 2
fi

"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/train_rfdetr_ab.py" \
    --data "$DATA_ROOT" \
    --output "$RUN_DIR" \
    --run "$RUN_NAME" \
    --raw-class-weights 1,1,1,1 \
    --epochs "$TARGET_EPOCHS" \
    --eval-interval "$TARGET_EPOCHS" \
    --batch-size 19 \
    --seed 42 \
    --lr 3e-5 \
    --lr-encoder 3e-6 \
    "${checkpoint_args[@]}"
