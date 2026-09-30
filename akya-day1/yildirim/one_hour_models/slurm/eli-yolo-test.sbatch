#!/bin/bash
#SBATCH --job-name=eli-yolo-test
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=64G
#SBATCH --time=00:40:00

set -euo pipefail

: "${CHECKPOINT:?CHECKPOINT must be set}"
: "${OUTPUT_DIR:?OUTPUT_DIR must be set}"

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon/akya-day1
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"

module purge
module load Python/3.12.3-GCCcore-13.3.0
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export YOLO_CONFIG_DIR="$ELI_ROOT/runs/yolo-config"
export OMP_NUM_THREADS=8

cd "$SOURCE_DIR"
"$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/predict_yolo_test.py" \
    --images "$REMOTE_REPO/data/test/images" \
    --checkpoint "$CHECKPOINT" \
    --output "$OUTPUT_DIR" \
    --batch-size 32 \
    --tile-size 704 \
    --tile-overlap 0.25 \
    --score-threshold 0.001 \
    --max-det 500 \
    --nms-iou 0.60 \
    --min-area 200 \
    --sample-submission "$REMOTE_REPO/data/sample_submission.csv" \
    --submission "$OUTPUT_DIR/submission.csv"
