#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR="$ELI_ROOT/logs"
mkdir -p "$LOG_DIR"

prep_job=$(sbatch --parsable \
    --output="$LOG_DIR/eli-yolo-prep-%j.out" \
    --error="$LOG_DIR/eli-yolo-prep-%j.err" \
    "$SLURM_DIR/eli-yolo-sliced-prep.sbatch")
echo "eli-yolo-prep=$prep_job"

p1_job=$(sbatch --parsable \
    --job-name=eli-yolo-p1 \
    --dependency="afterok:$prep_job" \
    --export="ALL,PILOT=1,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-yolo-p1-%j.out" \
    --error="$LOG_DIR/eli-yolo-p1-%j.err" \
    "$SLURM_DIR/eli-yolo-sliced-train.sbatch")
echo "eli-yolo-p1=$p1_job"

p2_job=$(sbatch --parsable \
    --job-name=eli-yolo-p2 \
    --dependency="afterok:$prep_job" \
    --export="ALL,PILOT=2,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-yolo-p2-%j.out" \
    --error="$LOG_DIR/eli-yolo-p2-%j.err" \
    "$SLURM_DIR/eli-yolo-sliced-train.sbatch")
echo "eli-yolo-p2=$p2_job"

p1_eval=$(sbatch --parsable \
    --job-name=eli-yolo-p1-eval \
    --dependency="afterok:$p1_job" \
    --export=ALL,PILOT=1 \
    --output="$LOG_DIR/eli-yolo-p1-eval-%j.out" \
    --error="$LOG_DIR/eli-yolo-p1-eval-%j.err" \
    "$SLURM_DIR/eli-yolo-sliced-eval.sbatch")
echo "eli-yolo-p1-eval=$p1_eval"

p2_eval=$(sbatch --parsable \
    --job-name=eli-yolo-p2-eval \
    --dependency="afterok:$p2_job" \
    --export=ALL,PILOT=2 \
    --output="$LOG_DIR/eli-yolo-p2-eval-%j.out" \
    --error="$LOG_DIR/eli-yolo-p2-eval-%j.err" \
    "$SLURM_DIR/eli-yolo-sliced-eval.sbatch")
echo "eli-yolo-p2-eval=$p2_eval"

select_job=$(sbatch --parsable \
    --dependency="afterok:$p1_eval:$p2_eval" \
    --output="$LOG_DIR/eli-yolo-select-%j.out" \
    --error="$LOG_DIR/eli-yolo-select-%j.err" \
    "$SLURM_DIR/eli-yolo-sliced-select.sbatch")
echo "eli-yolo-select=$select_job"

p3_job=$(sbatch --parsable \
    --job-name=eli-yolo-p3 \
    --dependency="afterok:$select_job" \
    --export="ALL,PILOT=3,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-yolo-p3-%j.out" \
    --error="$LOG_DIR/eli-yolo-p3-%j.err" \
    "$SLURM_DIR/eli-yolo-sliced-train.sbatch")
echo "eli-yolo-p3=$p3_job"

p3_eval=$(sbatch --parsable \
    --job-name=eli-yolo-p3-eval \
    --dependency="afterok:$p3_job" \
    --export=ALL,PILOT=3 \
    --output="$LOG_DIR/eli-yolo-p3-eval-%j.out" \
    --error="$LOG_DIR/eli-yolo-p3-eval-%j.err" \
    "$SLURM_DIR/eli-yolo-sliced-eval.sbatch")
echo "eli-yolo-p3-eval=$p3_eval"
