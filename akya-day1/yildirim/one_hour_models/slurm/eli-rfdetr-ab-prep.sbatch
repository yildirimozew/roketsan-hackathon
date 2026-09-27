#!/bin/bash
#SBATCH --job-name=eli-rfdetr-ab-prep
#SBATCH --account=open-37-16
#SBATCH --partition=qcpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=04:00:00

set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
RFDETR_REPO="$ELI_ROOT/repos/rf-detr"
RFDETR_COMMIT=4f68814adb3df5a1ac4769fc11f7b32d8e2d404f
PREPARED="$ELI_ROOT/prepared/rfdetr_scene_ab"

module purge
module load Python/3.12.3-GCCcore-13.3.0
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export OMP_NUM_THREADS=8

test "$(git -C "$RFDETR_REPO" rev-parse HEAD)" = "$RFDETR_COMMIT"
if git -C "$RFDETR_REPO" apply --reverse --check "$SOURCE_DIR/rfdetr_class_weights.patch" >/dev/null 2>&1; then
    echo "RF-DETR class-weight patch already applied"
else
    git -C "$RFDETR_REPO" apply --check "$SOURCE_DIR/rfdetr_class_weights.patch"
    git -C "$RFDETR_REPO" apply "$SOURCE_DIR/rfdetr_class_weights.patch"
fi
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/verify_rfdetr_class_weights.py"

if [[ -f "$PREPARED/READY.json" ]]; then
    "$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/check_rfdetr_ab.py" --prepared "$PREPARED"
    exit 0
fi
if [[ -e "$PREPARED" ]]; then
    echo "Refusing to replace incomplete prepared directory: $PREPARED" >&2
    exit 1
fi

BUILD="$ELI_ROOT/prepared/.rfdetr_scene_ab.build-$SLURM_JOB_ID"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/prepare_rfdetr_ab.py" \
    --repo "$REMOTE_REPO" \
    --split-dir "$REMOTE_REPO/splits/scene_holdout_v1" \
    --output "$BUILD"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/check_rfdetr_ab.py" --prepared "$BUILD"
mv "$BUILD" "$PREPARED"
