#!/bin/bash
#SBATCH --job-name=eli-yolo-prep
#SBATCH --account=open-37-16
#SBATCH --partition=qcpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=04:00:00

set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon/akya-day1
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
PREPARED="${PREPARED:-$ELI_ROOT/prepared/yolo_scene_pilots}"
prep_args=()
if [[ "${TRAIN_ON_ALL:-0}" == "1" ]]; then
    prep_args+=(--train-on-all --centered-ratios 0.25)
fi

module purge
module load Python/3.12.3-GCCcore-13.3.0
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export YOLO_CONFIG_DIR="$ELI_ROOT/runs/yolo-config"
export OMP_NUM_THREADS=8

if [[ -f "$PREPARED/READY.json" ]]; then
    "$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/check_yolo_sliced.py" \
        --prepared "$PREPARED" --repo "$REMOTE_REPO"
else
    if [[ -e "$PREPARED" ]]; then
        echo "Refusing to replace incomplete prepared directory: $PREPARED" >&2
        exit 1
    fi
    BUILD="$(dirname "$PREPARED")/.$(basename "$PREPARED").build-$SLURM_JOB_ID"
    "$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/prepare_yolo_sliced.py" \
        --repo "$REMOTE_REPO" \
        --split-dir "$REMOTE_REPO/splits/scene_holdout_v2" \
        --output "$BUILD" \
        "${prep_args[@]}"
    "$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/check_yolo_sliced.py" \
        --prepared "$BUILD" --repo "$REMOTE_REPO"
    mv "$BUILD" "$PREPARED"
fi

# Build the shared ratio-25 label cache once so pilots 1 and 2 only read it.
cd "$PREPARED"
"$ELI_ROOT/venvs/yolo/bin/python" - <<'PY'
from ultralytics.data.dataset import YOLODataset
from ultralytics.data.utils import check_det_dataset

data = check_det_dataset("dataset_ratio25.yaml")
dataset = YOLODataset(img_path=data["train"], data=data, task="detect", augment=False, prefix="ratio25: ")
print(f"cached {len(dataset)} ratio-25 training images")
PY
