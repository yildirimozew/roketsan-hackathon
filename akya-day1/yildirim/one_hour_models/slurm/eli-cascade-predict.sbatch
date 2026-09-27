#!/bin/bash
#SBATCH --job-name=eli-cascade-predict
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=00:45:00
#SBATCH --output=/mnt/proj1/open-37-16/yildirimozew/eli-training/logs/%x-%j.out
#SBATCH --error=/mnt/proj1/open-37-16/yildirimozew/eli-training/logs/%x-%j.err

set -euo pipefail
module purge
module load Python/3.11.3-GCCcore-12.3.0 CUDA/12.1.1

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
MMDET="$ELI_ROOT/repos/mmdetection"
CONFIG="$MMDET/configs/eli/cascade_eli_convnext_t.py"
CHECKPOINT="$ELI_ROOT/runs/cascade_convnext_t/epoch_5.pth"
OUTPUT="$ELI_ROOT/runs/cascade_convnext_t/ensemble_predictions"
PYTHON="$ELI_ROOT/venvs/mmdet/bin/python"
PREDICT="$REMOTE_REPO/yildirim/one_hour_models/predict_cascade.py"

export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export PYTHONPATH="$MMDET${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=8
export WANDB_MODE=disabled
mkdir -p "$OUTPUT"

"$PYTHON" "$PREDICT" \
    --config "$CONFIG" \
    --checkpoint "$CHECKPOINT" \
    --images "$REMOTE_REPO/data/train/images" \
    --image-ids "$REMOTE_REPO/splits/folds/fold_1_val.txt" \
    --output "$OUTPUT/preds_val_fold1.csv" \
    --batch-size 2 \
    --score-threshold 0.001

"$PYTHON" "$PREDICT" \
    --config "$CONFIG" \
    --checkpoint "$CHECKPOINT" \
    --images "$REMOTE_REPO/data/test/images" \
    --output "$OUTPUT/preds_test.csv" \
    --batch-size 2 \
    --score-threshold 0.001
