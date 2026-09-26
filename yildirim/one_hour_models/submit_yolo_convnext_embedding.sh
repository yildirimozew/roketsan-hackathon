#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR="$ELI_ROOT/logs"
mkdir -p "$LOG_DIR"

prep=$(sbatch --parsable \
    --output="$LOG_DIR/eli-yolo-cv-prep-%j.out" --error="$LOG_DIR/eli-yolo-cv-prep-%j.err" \
    "$SLURM_DIR/eli-yolo-cv-prep.sbatch")
train=$(sbatch --parsable --dependency="afterok:$prep" \
    --output="$LOG_DIR/eli-yolo-cv-train-%j.out" --error="$LOG_DIR/eli-yolo-cv-train-%j.err" \
    "$SLURM_DIR/eli-yolo-cv-train.sbatch")
embed=$(sbatch --parsable --dependency="afterok:$train" \
    --output="$LOG_DIR/eli-yolo-cv-embed-%j.out" --error="$LOG_DIR/eli-yolo-cv-embed-%j.err" \
    "$SLURM_DIR/eli-yolo-cv-embed.sbatch")
evaluation=$(sbatch --parsable --dependency="afterok:$embed" \
    --output="$LOG_DIR/eli-yolo-cv-eval-%j.out" --error="$LOG_DIR/eli-yolo-cv-eval-%j.err" \
    "$SLURM_DIR/eli-yolo-cv-eval.sbatch")

echo "eli-yolo-cv-prep=$prep"
echo "eli-yolo-cv-train=$train"
echo "eli-yolo-cv-embed=$embed"
echo "eli-yolo-cv-eval=$evaluation"
