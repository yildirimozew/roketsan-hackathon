#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon/akya-day1
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR="$ELI_ROOT/logs"
PREPARED="$ELI_ROOT/prepared/yolo_full_v2"
RUN_DIR="$ELI_ROOT/runs/yolo_full_v2_from_best"
WEIGHTS="$ELI_ROOT/runs/yolo_scene_full_v2/train/weights/best.pt"
EPOCHS="${EPOCHS:-3}"
mkdir -p "$LOG_DIR"

if [[ -e "$RUN_DIR" ]]; then
    echo "Refusing to reuse existing run directory: $RUN_DIR" >&2
    exit 1
fi
test -f "$WEIGHTS"

prep_job=$(sbatch --parsable \
    --job-name=eli-yolo-full-data-prep \
    --partition=qcpu_exp \
    --time=00:50:00 \
    --export="ALL,PREPARED=$PREPARED,TRAIN_ON_ALL=1" \
    --output="$LOG_DIR/eli-yolo-full-data-prep-%j.out" \
    --error="$LOG_DIR/eli-yolo-full-data-prep-%j.err" \
    "$SLURM_DIR/eli-yolo-sliced-prep.sbatch")
echo "eli-yolo-full-data-prep=$prep_job"

# Fine-tune the scene_holdout_v2 best weights on all 6,471 images. Validation
# images are part of training, so test predictions use the final weights.
train_job=$(sbatch --parsable \
    --job-name=eli-yolo-full-data \
    --dependency="afterok:$prep_job" \
    --export="ALL,PREPARED=$PREPARED,WEIGHTS=$WEIGHTS,RUN_DIR=$RUN_DIR,EPOCHS=$EPOCHS,RUN_NAME=yolo26-full-v2-finetune-e$EPOCHS,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
    --output="$LOG_DIR/eli-yolo-full-data-%j.out" \
    --error="$LOG_DIR/eli-yolo-full-data-%j.err" \
    "$SLURM_DIR/eli-yolo-finetune-full.sbatch")
echo "eli-yolo-full-data=$train_job"

predict_job=$(sbatch --parsable \
    --job-name=eli-yolo-full-data-test \
    --dependency="afterok:$train_job" \
    --export="ALL,CHECKPOINT=$RUN_DIR/train/weights/last.pt,OUTPUT_DIR=$RUN_DIR/test_predictions_e$EPOCHS" \
    --output="$LOG_DIR/eli-yolo-full-data-test-%j.out" \
    --error="$LOG_DIR/eli-yolo-full-data-test-%j.err" \
    "$SLURM_DIR/eli-yolo-test.sbatch")
echo "eli-yolo-full-data-test=$predict_job"
