#!/bin/bash
#SBATCH --job-name=eli-training-5
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=00:59:00

set -euo pipefail
module purge
module load Python/3.11.3-GCCcore-12.3.0 CUDA/12.1.1
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon/yildirim/one_hour_models
MMDET="$ELI_ROOT/repos/mmdetection"
CONFIG="$MMDET/configs/eli/cascade_eli_convnext_t.py"
OUTPUT="$ELI_ROOT/runs/cascade_convnext_t"
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export PYTHONPATH="$MMDET${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=8
source "$SOURCE_DIR/wandb_karolina.env"
export WANDB_RUN_GROUP=one-hour-pilots
export WANDB_NAME=eli-training-5
export WANDB_DIR="$ELI_ROOT/runs/wandb"
mkdir -p "$WANDB_DIR"
mkdir -p "$OUTPUT"
cd "$MMDET"

resume_args=()
if [[ -f "$OUTPUT/last_checkpoint" ]]; then
    resume_args=(--resume)
fi

set +e
timeout --signal=TERM --kill-after=60s 3000s \
    "$ELI_ROOT/venvs/mmdet/bin/python" tools/train.py "$CONFIG" \
    --work-dir "$OUTPUT" "${resume_args[@]}"
train_status=$?
set -e
if [[ $train_status -ne 0 && $train_status -ne 124 && $train_status -ne 143 ]]; then
    exit "$train_status"
fi
checkpoint=$(find "$OUTPUT" -maxdepth 1 -type f -name 'epoch_*.pth' -print | sort -V | tail -1)
test -n "$checkpoint"
echo "Training segment complete; newest checkpoint: $checkpoint"
