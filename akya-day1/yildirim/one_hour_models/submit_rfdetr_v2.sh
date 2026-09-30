#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon/akya-day1
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR="$ELI_ROOT/logs"
PREPARED="$ELI_ROOT/prepared/rfdetr_scene_v2"
RUN_DIR="$ELI_ROOT/runs/rfdetr_scene_v2_a"
EPOCHS="${EPOCHS:-12}"
mkdir -p "$LOG_DIR"

if [[ -e "$RUN_DIR" ]]; then
    echo "Refusing to reuse existing run directory: $RUN_DIR" >&2
    exit 1
fi

prep_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-v2-prep \
    --export="ALL,SPLIT_NAME=scene_holdout_v2,PREPARED=$PREPARED" \
    --output="$LOG_DIR/eli-rfdetr-v2-prep-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-v2-prep-%j.err" \
    "$SLURM_DIR/eli-rfdetr-ab-prep.sbatch")
echo "eli-rfdetr-v2-prep=$prep_job"

# Arm A recipe (unweighted, 25% rare-class-centred crops) from COCO weights,
# as one qgpu job instead of chained qgpu_exp segments.
train_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-v2-a \
    --partition=qgpu \
    --time=04:30:00 \
    --dependency="afterok:$prep_job" \
    --export="ALL,AB_ARM=a,PREPARED=$PREPARED,RUN_DIR=$RUN_DIR,RUN_NAME=rfdetr-scene-v2-a-train,EPOCHS=$EPOCHS,EVAL_INTERVAL=3,WANDB_RUN_GROUP=rfdetr-scene-v2,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-rfdetr-v2-a-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-v2-a-%j.err" \
    "$SLURM_DIR/eli-rfdetr-ab-train.sbatch")
echo "eli-rfdetr-v2-a=$train_job"

eval_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-v2-a-eval \
    --dependency="afterok:$train_job" \
    --export="ALL,AB_ARM=a,PREPARED=$PREPARED,RUN_DIR=$RUN_DIR,RUN_NAME=rfdetr-scene-v2-a-eval,WANDB_RUN_GROUP=rfdetr-scene-v2" \
    --output="$LOG_DIR/eli-rfdetr-v2-a-eval-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-v2-a-eval-%j.err" \
    "$SLURM_DIR/eli-rfdetr-ab-eval.sbatch")
echo "eli-rfdetr-v2-a-eval=$eval_job"

predict_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-v2-a-test \
    --dependency="afterok:$eval_job" \
    --export="ALL,RUN_DIR=$RUN_DIR,CHECKPOINT=$RUN_DIR/checkpoint_best_ema.pth,OUTPUT_DIR=$RUN_DIR/test_predictions" \
    --output="$LOG_DIR/eli-rfdetr-v2-a-test-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-v2-a-test-%j.err" \
    "$SLURM_DIR/eli-rfdetr-test.sbatch")
echo "eli-rfdetr-v2-a-test=$predict_job"
