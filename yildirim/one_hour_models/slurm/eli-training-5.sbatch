#!/bin/bash
#SBATCH --job-name=eli-training-5
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=02:30:00

set -euo pipefail
module purge
module load PyTorch/2.1.2-foss-2023a-CUDA-12.1.1
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
MMDET="$ELI_ROOT/repos/mmdetection"
CONFIG="$MMDET/configs/eli/cascade_eli_convnext_t.py"
OUTPUT="$ELI_ROOT/runs/cascade_convnext_t"
export OMP_NUM_THREADS=8
export WANDB_PROJECT=eli-training
export WANDB_RUN_GROUP=one-hour-pilots
export WANDB_NAME=eli-training-5
export WANDB_DIR="$ELI_ROOT/runs/wandb"
export WANDB_SILENT=true
mkdir -p "$WANDB_DIR"
mkdir -p "$OUTPUT"
cd "$MMDET"
set +e
timeout --signal=TERM --kill-after=120s 3600s \
    "$ELI_ROOT/venvs/mmdet/bin/python" tools/train.py "$CONFIG" \
    --work-dir "$OUTPUT"
train_status=$?
set -e
if [[ $train_status -ne 0 && $train_status -ne 124 && $train_status -ne 143 ]]; then
    exit "$train_status"
fi
checkpoint=$(find "$OUTPUT" -maxdepth 1 -type f -name 'epoch_*.pth' -print | sort -V | tail -1)
test -n "$checkpoint"
"$ELI_ROOT/venvs/mmdet/bin/python" tools/test.py "$CONFIG" "$checkpoint" \
    --work-dir "$OUTPUT/evaluation"
