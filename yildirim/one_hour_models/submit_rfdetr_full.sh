#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR="$ELI_ROOT/logs"
RUN_DIR="$ELI_ROOT/runs/rfdetr_full_v1_from_e12"
SOURCE_RUN="$ELI_ROOT/runs/rfdetr_scene_a"
mkdir -p "$LOG_DIR"

if [[ -e "$RUN_DIR" ]]; then
    echo "Refusing to reuse existing run directory: $RUN_DIR" >&2
    exit 1
fi
test -f "$SOURCE_RUN/checkpoint_epoch12_best_ema.pth"

prep_job=$(sbatch --parsable \
    --output="$LOG_DIR/eli-rfdetr-full-prep-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-full-prep-%j.err" \
    "$SLURM_DIR/eli-rfdetr-full-prep.sbatch")
echo "eli-rfdetr-full-prep=$prep_job"

train_2_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-full-e2 \
    --dependency="afterok:$prep_job" \
    --export="ALL,TARGET_EPOCHS=2,INIT_WEIGHTS=$SOURCE_RUN/checkpoint_epoch12_best_ema.pth,RUN_NAME=rfdetr-full-v1-from-e12-e2,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-rfdetr-full-e2-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-full-e2-%j.err" \
    "$SLURM_DIR/eli-rfdetr-full-train.sbatch")
echo "eli-rfdetr-full-e2=$train_2_job"

train_3_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-full-e3 \
    --dependency="afterok:$train_2_job" \
    --export="ALL,TARGET_EPOCHS=3,RESUME_CHECKPOINT=$RUN_DIR/checkpoint_1.ckpt,RUN_NAME=rfdetr-full-v1-from-e12-e3,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-rfdetr-full-e3-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-full-e3-%j.err" \
    "$SLURM_DIR/eli-rfdetr-full-train.sbatch")
echo "eli-rfdetr-full-e3=$train_3_job"

predict_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-full-test \
    --dependency="afterok:$train_3_job" \
    --export="ALL,RUN_DIR=$RUN_DIR,CHECKPOINT=$RUN_DIR/last_ema.pth,OUTPUT_DIR=$RUN_DIR/test_predictions_e3" \
    --output="$LOG_DIR/eli-rfdetr-full-test-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-full-test-%j.err" \
    "$SLURM_DIR/eli-rfdetr-test.sbatch")
echo "eli-rfdetr-full-test=$predict_job"
