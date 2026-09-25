#!/bin/bash
#SBATCH --job-name=eli-cv-submit
#SBATCH --account=open-37-16
#SBATCH --partition=qcpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=00:20:00

set -euo pipefail
module purge
module load Python/3.12.3-GCCcore-13.3.0

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
RUN_DIR="$ELI_ROOT/runs/rfdetr_convnext_cv"
OUTPUT="$RUN_DIR/test_predictions"

test ! -e "$OUTPUT"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/rfdetr_convnext_fusion.py" submit \
    --features "$RUN_DIR/test_features" \
    --calibration "$RUN_DIR/calibration/calibration.json" \
    --sample-submission "$REMOTE_REPO/data/sample_submission.csv" \
    --output "$OUTPUT"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$REMOTE_REPO/ardahan/check_submission.py" "$OUTPUT/submission.csv"
