#!/bin/bash
#SBATCH --job-name=eli-yolo-cv-prep
#SBATCH --account=open-37-16
#SBATCH --partition=qcpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=64G
#SBATCH --time=00:40:00

set -euo pipefail
module purge
module load Python/3.12.3-GCCcore-13.3.0

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
OUTPUT="$ELI_ROOT/prepared/convnext_cv_v2"
BUILD="$ELI_ROOT/prepared/.convnext_cv_v2.build-$SLURM_JOB_ID"

test ! -e "$OUTPUT"
test ! -e "$BUILD"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/prepare_convnext_cv.py" \
    --annotations "$REMOTE_REPO/data/train/annotations.csv" \
    --images "$REMOTE_REPO/data/train/images" \
    --split "$REMOTE_REPO/splits/scene_holdout_v2" \
    --output "$BUILD" \
    --context 1.75 \
    --size 224 \
    --seed 42 \
    --workers 24 \
    --dataset-name convnext-tiny-car-van-scene-holdout-v2
mv "$BUILD" "$OUTPUT"
