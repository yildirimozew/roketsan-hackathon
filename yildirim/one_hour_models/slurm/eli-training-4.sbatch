#!/bin/bash
#SBATCH --job-name=eli-training-4
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
module load Python/3.12.3-GCCcore-13.3.0
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
DFINE="$ELI_ROOT/repos/D-FINE"
CONFIG="$DFINE/configs/dfine/dfine_eli_l.yml"
OUTPUT="$ELI_ROOT/runs/dfine_l"
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export OMP_NUM_THREADS=8
export WANDB_PROJECT=eli-training
export WANDB_RUN_GROUP=one-hour-pilots
export WANDB_NAME=eli-training-4
export WANDB_DIR="$ELI_ROOT/runs/wandb"
export WANDB_SILENT=true
mkdir -p "$WANDB_DIR"
mkdir -p "$OUTPUT"
cd "$DFINE"
set +e
timeout --signal=TERM --kill-after=120s 3600s \
    "$ELI_ROOT/venvs/dfine/bin/python" train.py \
    -c "$CONFIG" --use-amp --seed 42 --output-dir "$OUTPUT" \
    -t "$ELI_ROOT/weights/dfine_l_coco.pth"
train_status=$?
set -e
if [[ $train_status -ne 0 && $train_status -ne 124 && $train_status -ne 143 ]]; then
    exit "$train_status"
fi
test -f "$OUTPUT/last.pth"
"$ELI_ROOT/venvs/dfine/bin/python" train.py \
    -c "$CONFIG" --use-amp --seed 42 --output-dir "$OUTPUT/evaluation" \
    --test-only -r "$OUTPUT/last.pth"
