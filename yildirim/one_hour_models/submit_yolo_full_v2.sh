#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR="$ELI_ROOT/logs"
RUN_DIR="$ELI_ROOT/runs/yolo_scene_full_v2"
mkdir -p "$LOG_DIR"

if [[ -e "$RUN_DIR/train/results.csv" || -e "$RUN_DIR/training_summary.json" ]]; then
    echo "Refusing to overwrite existing full-run output in $RUN_DIR" >&2
    exit 3
fi

train_job=$(sbatch --parsable \
    --job-name=eli-yolo-full \
    --export="ALL,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-yolo-full-%j.out" \
    --error="$LOG_DIR/eli-yolo-full-%j.err" \
    "$SLURM_DIR/eli-yolo-full-v2-train.sbatch")
echo "eli-yolo-full=$train_job"

eval_job=$(sbatch --parsable \
    --job-name=eli-yolo-full-eval \
    --dependency="afterok:$train_job" \
    --output="$LOG_DIR/eli-yolo-full-eval-%j.out" \
    --error="$LOG_DIR/eli-yolo-full-eval-%j.err" \
    "$SLURM_DIR/eli-yolo-full-v2-eval.sbatch")
echo "eli-yolo-full-eval=$eval_job"
