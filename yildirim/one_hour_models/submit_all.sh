#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR=/mnt/proj1/open-37-16/yildirimozew/eli-training/logs
mkdir -p "$LOG_DIR"

prep_job=$(sbatch --parsable \
    --output="$LOG_DIR/eli-prep-%j.out" \
    --error="$LOG_DIR/eli-prep-%j.err" \
    "$SLURM_DIR/eli-prep.sbatch")
echo "eli-prep=$prep_job"

for number in 1 2 3 4 5; do
    job_id=$(sbatch --parsable \
        --dependency="afterok:$prep_job" \
        --output="$LOG_DIR/eli-training-$number-%j.out" \
        --error="$LOG_DIR/eli-training-$number-%j.err" \
        "$SLURM_DIR/eli-training-$number.sbatch")
    echo "eli-training-$number=$job_id"
done
