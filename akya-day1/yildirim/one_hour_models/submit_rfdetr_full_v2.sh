#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon/akya-day1
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR="$ELI_ROOT/logs"
PREPARED="$ELI_ROOT/prepared/rfdetr_full_v2"
RUN_DIR="$ELI_ROOT/runs/rfdetr_full_v2_from_e12"
INIT_WEIGHTS="$ELI_ROOT/runs/rfdetr_scene_v2_a/checkpoint_best_ema.pth"
EPOCHS="${EPOCHS:-3}"
mkdir -p "$LOG_DIR"

if [[ -e "$RUN_DIR" ]]; then
    echo "Refusing to reuse existing run directory: $RUN_DIR" >&2
    exit 1
fi
test -f "$INIT_WEIGHTS"

prep_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-full-v2-prep \
    --partition=qcpu_exp \
    --time=00:45:00 \
    --export="ALL,SPLIT_NAME=scene_holdout_v2,PREPARED=$PREPARED" \
    --output="$LOG_DIR/eli-rfdetr-full-v2-prep-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-full-v2-prep-%j.err" \
    "$SLURM_DIR/eli-rfdetr-full-prep.sbatch")
echo "eli-rfdetr-full-v2-prep=$prep_job"

# Fine-tune the v2 epoch-12 EMA weights on all 6,471 images in one qgpu job.
# Validation images are part of training here, so its val score is only a
# sanity check and the test predictions use the final EMA weights.
train_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-full-v2 \
    --partition=qgpu \
    --time=01:45:00 \
    --dependency="afterok:$prep_job" \
    --export="ALL,TARGET_EPOCHS=$EPOCHS,INIT_WEIGHTS=$INIT_WEIGHTS,PREPARED=$PREPARED,RUN_DIR=$RUN_DIR,RUN_NAME=rfdetr-full-v2-from-e12-e$EPOCHS,WANDB_RUN_GROUP=rfdetr-full-v2-from-e12,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-rfdetr-full-v2-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-full-v2-%j.err" \
    "$SLURM_DIR/eli-rfdetr-full-train.sbatch")
echo "eli-rfdetr-full-v2=$train_job"

predict_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-full-v2-test \
    --dependency="afterok:$train_job" \
    --export="ALL,RUN_DIR=$RUN_DIR,CHECKPOINT=$RUN_DIR/last_ema.pth,OUTPUT_DIR=$RUN_DIR/test_predictions_e$EPOCHS" \
    --output="$LOG_DIR/eli-rfdetr-full-v2-test-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-full-v2-test-%j.err" \
    "$SLURM_DIR/eli-rfdetr-test.sbatch")
echo "eli-rfdetr-full-v2-test=$predict_job"
