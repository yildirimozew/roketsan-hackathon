#!/bin/bash
set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SLURM_DIR="$REMOTE_REPO/yildirim/one_hour_models/slurm"
LOG_DIR="$ELI_ROOT/logs"
WEIGHTS="$ELI_ROOT/weights/convnext_tiny-983f1562.pth"
LONG_JOB="${LONG_JOB:-5113798}"
mkdir -p "$LOG_DIR" "$ELI_ROOT/weights"

if [[ ! -f "$WEIGHTS" ]]; then
    curl --fail --location --retry 3 \
        https://download.pytorch.org/models/convnext_tiny-983f1562.pth \
        --output "$WEIGHTS"
fi
hash=$(sha256sum "$WEIGHTS" | awk '{print $1}')
[[ "$hash" == 983f1562* ]] || { echo "unexpected ConvNeXt weight hash: $hash" >&2; exit 1; }

prep=$(sbatch --parsable \
    --output="$LOG_DIR/eli-cv-prep-%j.out" --error="$LOG_DIR/eli-cv-prep-%j.err" \
    "$SLURM_DIR/eli-cv-prep.sbatch")
train=$(sbatch --parsable --dependency="afterok:$prep" \
    --output="$LOG_DIR/eli-cv-train-%j.out" --error="$LOG_DIR/eli-cv-train-%j.err" \
    "$SLURM_DIR/eli-cv-train.sbatch")
validation=$(sbatch --parsable --dependency="afterok:$train:$LONG_JOB" \
    --output="$LOG_DIR/eli-cv-val-%j.out" --error="$LOG_DIR/eli-cv-val-%j.err" \
    "$SLURM_DIR/eli-cv-val.sbatch")
calibration=$(sbatch --parsable --dependency="afterok:$validation" \
    --output="$LOG_DIR/eli-cv-calibrate-%j.out" --error="$LOG_DIR/eli-cv-calibrate-%j.err" \
    "$SLURM_DIR/eli-cv-calibrate.sbatch")
test_job=$(sbatch --parsable --dependency="afterok:$calibration" \
    --output="$LOG_DIR/eli-cv-test-%j.out" --error="$LOG_DIR/eli-cv-test-%j.err" \
    "$SLURM_DIR/eli-cv-test.sbatch")
submit_job=$(sbatch --parsable --dependency="afterok:$test_job" \
    --output="$LOG_DIR/eli-cv-submit-%j.out" --error="$LOG_DIR/eli-cv-submit-%j.err" \
    "$SLURM_DIR/eli-cv-submit.sbatch")

echo "eli-cv-prep=$prep"
echo "eli-cv-train=$train"
echo "eli-cv-val=$validation"
echo "eli-cv-calibrate=$calibration"
echo "eli-cv-test=$test_job"
echo "eli-cv-submit=$submit_job"
