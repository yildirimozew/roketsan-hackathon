#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR="$ELI_ROOT/logs"
mkdir -p "$LOG_DIR"

prep_job=$(sbatch --parsable \
    --output="$LOG_DIR/eli-rfdetr-ab-prep-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-ab-prep-%j.err" \
    "$SLURM_DIR/eli-rfdetr-ab-prep.sbatch")
echo "eli-rfdetr-ab-prep=$prep_job"

a_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-a \
    --dependency="afterok:$prep_job" \
    --export="ALL,AB_ARM=a,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-rfdetr-a-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-a-%j.err" \
    "$SLURM_DIR/eli-rfdetr-ab-train.sbatch")
echo "eli-rfdetr-a=$a_job"

b_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-b \
    --dependency="afterok:$prep_job" \
    --export="ALL,AB_ARM=b,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-rfdetr-b-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-b-%j.err" \
    "$SLURM_DIR/eli-rfdetr-ab-train.sbatch")
echo "eli-rfdetr-b=$b_job"

both="afterok:$a_job:$b_job"
a_eval=$(sbatch --parsable \
    --job-name=eli-rfdetr-a-eval \
    --dependency="$both" \
    --export=ALL,AB_ARM=a \
    --output="$LOG_DIR/eli-rfdetr-a-eval-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-a-eval-%j.err" \
    "$SLURM_DIR/eli-rfdetr-ab-eval.sbatch")
echo "eli-rfdetr-a-eval=$a_eval"

b_eval=$(sbatch --parsable \
    --job-name=eli-rfdetr-b-eval \
    --dependency="$both" \
    --export=ALL,AB_ARM=b \
    --output="$LOG_DIR/eli-rfdetr-b-eval-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-b-eval-%j.err" \
    "$SLURM_DIR/eli-rfdetr-ab-eval.sbatch")
echo "eli-rfdetr-b-eval=$b_eval"
