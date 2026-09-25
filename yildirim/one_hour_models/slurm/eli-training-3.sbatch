#!/bin/bash
#SBATCH --job-name=eli-training-3
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
SOURCE_DIR=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon/yildirim/one_hour_models
export OMP_NUM_THREADS=8
export WANDB_PROJECT=eli-training
export WANDB_RUN_GROUP=one-hour-pilots
export WANDB_NAME=eli-training-3
export WANDB_DIR="$ELI_ROOT/runs/wandb"
export WANDB_SILENT=true
mkdir -p "$WANDB_DIR"
"$ELI_ROOT/venvs/rfdetr/bin/python" - <<'PY'
from rfdetr import RFDETRLarge
RFDETRLarge(resolution=704)
PY
set +e
timeout --signal=TERM --kill-after=120s 3600s \
    "$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/train_rfdetr.py" \
    --data "$ELI_ROOT/prepared/rfdetr_tiles" \
    --output "$ELI_ROOT/runs/rfdetr_large"
train_status=$?
set -e
if [[ $train_status -ne 0 && $train_status -ne 124 && $train_status -ne 143 ]]; then
    exit "$train_status"
fi
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/evaluate_rfdetr.py" \
    --data "$ELI_ROOT/prepared/rfdetr_tiles" \
    --output "$ELI_ROOT/runs/rfdetr_large"
