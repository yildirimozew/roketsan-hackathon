#!/bin/bash
#SBATCH --job-name=eli-rfdetr-test
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=/mnt/proj1/open-37-16/yildirimozew/eli-training/logs/%x-%j.out
#SBATCH --error=/mnt/proj1/open-37-16/yildirimozew/eli-training/logs/%x-%j.err

set -euo pipefail
module purge
module load Python/3.12.3-GCCcore-13.3.0

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export WANDB_MODE=disabled
export OMP_NUM_THREADS=8

"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/predict_rfdetr_test.py" \
    --images "$REMOTE_REPO/data/test/images" \
    --checkpoint "$ELI_ROOT/runs/rfdetr_large/checkpoint_best_ema.pth" \
    --output "$ELI_ROOT/runs/rfdetr_large/test_predictions" \
    --batch-size 16 \
    --tile-size 704 \
    --tile-overlap 0.25 \
    --score-threshold 0.001 \
    --max-det 1000 \
    --nms-iou 0.6
