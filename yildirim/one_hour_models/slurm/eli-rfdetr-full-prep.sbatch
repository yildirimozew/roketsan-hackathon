#!/bin/bash
#SBATCH --job-name=eli-rfdetr-full-prep
#SBATCH --account=open-37-16
#SBATCH --partition=qcpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=04:00:00

set -euo pipefail

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
PREPARED="$ELI_ROOT/prepared/rfdetr_full_v1"

module purge
module load Python/3.12.3-GCCcore-13.3.0
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export OMP_NUM_THREADS=8

if [[ -f "$PREPARED/READY.json" ]]; then
    "$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/check_rfdetr_ab.py" --prepared "$PREPARED"
    exit 0
fi
if [[ -e "$PREPARED" ]]; then
    echo "Refusing to replace incomplete prepared directory: $PREPARED" >&2
    exit 1
fi

BUILD="$(dirname "$PREPARED")/.$(basename "$PREPARED").build-$SLURM_JOB_ID"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/prepare_rfdetr_ab.py" \
    --repo "$REMOTE_REPO" \
    --split-dir "$REMOTE_REPO/splits/scene_holdout_v1" \
    --output "$BUILD" \
    --train-on-all
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/check_rfdetr_ab.py" --prepared "$BUILD"
mv "$BUILD" "$PREPARED"
