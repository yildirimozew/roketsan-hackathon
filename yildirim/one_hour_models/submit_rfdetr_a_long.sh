#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR="$ELI_ROOT/logs"
RUN_DIR="$ELI_ROOT/runs/rfdetr_scene_a"
mkdir -p "$LOG_DIR"

dependency=""
resume="$RUN_DIR/checkpoint_2.ckpt"
last_job=""
for target in 6 9 12 15; do
    dependency_args=()
    if [[ -n "$dependency" ]]; then
        dependency_args+=(--dependency="afterok:$dependency")
    fi
    job=$(sbatch --parsable \
        --job-name="eli-rfdetr-a-e${target}" \
        "${dependency_args[@]}" \
        --export="ALL,TARGET_EPOCH=$target,RESUME_CHECKPOINT=$resume,ELI_GIT_COMMIT=${ELI_GIT_COMMIT:-unknown}" \
        --output="$LOG_DIR/eli-rfdetr-a-e${target}-%j.out" \
        --error="$LOG_DIR/eli-rfdetr-a-e${target}-%j.err" \
        "$SLURM_DIR/eli-rfdetr-a-long-train.sbatch")
    echo "eli-rfdetr-a-e${target}=$job"
    dependency="$job"
    last_job="$job"
    resume="$RUN_DIR/checkpoint_$((target - 1)).ckpt"
done

eval_dir="$RUN_DIR/eval_original_long_e15"
eval_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-a-long-eval \
    --dependency="afterok:$last_job" \
    --export="ALL,AB_ARM=a,EVAL_DIR=$eval_dir,RUN_NAME=rfdetr-scene-a-long-eval,CHECKPOINT=$RUN_DIR/checkpoint_best_ema.pth" \
    --output="$LOG_DIR/eli-rfdetr-a-long-eval-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-a-long-eval-%j.err" \
    "$SLURM_DIR/eli-rfdetr-ab-eval.sbatch")
echo "eli-rfdetr-a-long-eval=$eval_job"

prediction_dir="$RUN_DIR/test_predictions_long_e15"
predict_job=$(sbatch --parsable \
    --job-name=eli-rfdetr-a-long-test \
    --dependency="afterok:$eval_job" \
    --export="ALL,RUN_DIR=$RUN_DIR,CHECKPOINT=$RUN_DIR/checkpoint_best_ema.pth,OUTPUT_DIR=$prediction_dir" \
    --output="$LOG_DIR/eli-rfdetr-a-long-test-%j.out" \
    --error="$LOG_DIR/eli-rfdetr-a-long-test-%j.err" \
    "$SLURM_DIR/eli-rfdetr-test.sbatch")
echo "eli-rfdetr-a-long-test=$predict_job"
