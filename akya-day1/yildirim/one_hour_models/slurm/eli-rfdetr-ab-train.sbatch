#!/bin/bash
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=00:59:00

set -euo pipefail

if [[ "${AB_ARM:-}" != "a" && "${AB_ARM:-}" != "b" ]]; then
    echo "AB_ARM must be a or b" >&2
    exit 2
fi

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
DATA_ROOT="$ELI_ROOT/prepared/rfdetr_scene_ab/rfdetr_tiles"
RUN_NAME="rfdetr-scene-$AB_ARM-train"
RUN_DIR="$ELI_ROOT/runs/rfdetr_scene_$AB_ARM"

module purge
module load Python/3.12.3-GCCcore-13.3.0
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export TORCHINDUCTOR_CACHE_DIR="$ELI_ROOT/cache/torchinductor/$RUN_NAME"
export OMP_NUM_THREADS=8
source "$SOURCE_DIR/wandb_karolina.env"
export WANDB_RUN_GROUP=rfdetr-scene-ab
export WANDB_NAME="$RUN_NAME"
export WANDB_DIR="$ELI_ROOT/runs/wandb/$RUN_NAME"
export ELI_GIT_COMMIT="${ELI_GIT_COMMIT:-unknown}"
mkdir -p "$WANDB_DIR" "$TORCHINDUCTOR_CACHE_DIR"

"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/check_rfdetr_ab.py" \
    --prepared "$ELI_ROOT/prepared/rfdetr_scene_ab"

if [[ "$AB_ARM" == "a" ]]; then
    RAW_WEIGHTS=1,1,1,1
else
    RAW_WEIGHTS=1,1.25,1.20,1.10
fi

"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/train_rfdetr_ab.py" \
    --data "$DATA_ROOT" \
    --output "$RUN_DIR" \
    --run "$RUN_NAME" \
    --raw-class-weights "$RAW_WEIGHTS" \
    --epochs 3 \
    --batch-size 19 \
    --seed 42
