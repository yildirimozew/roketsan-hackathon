#!/bin/bash
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=00:20:00

set -euo pipefail

if [[ "${AB_ARM:-}" != "a" && "${AB_ARM:-}" != "b" ]]; then
    echo "AB_ARM must be a or b" >&2
    exit 2
fi

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
PREPARED="$ELI_ROOT/prepared/rfdetr_scene_ab"
RUN_DIR="$ELI_ROOT/runs/rfdetr_scene_$AB_ARM"
EVAL_DIR="$RUN_DIR/eval_original"
RUN_NAME="rfdetr-scene-$AB_ARM-eval"
CHECKPOINT="$RUN_DIR/checkpoint_best_ema.pth"

module purge
module load Python/3.12.3-GCCcore-13.3.0
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export OMP_NUM_THREADS=8
export WANDB_ENTITY="${WANDB_ENTITY:-yildirimozew-eth-z-rich}"
export WANDB_PROJECT="${WANDB_PROJECT:-eli-training}"
export WANDB_RUN_GROUP=rfdetr-scene-ab
export WANDB_DIR="$ELI_ROOT/runs/wandb/$RUN_NAME"
export WANDB_MODE=offline
export WANDB_SILENT=true
mkdir -p "$WANDB_DIR"

test -f "$CHECKPOINT"
test ! -e "$EVAL_DIR"
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/evaluate_rfdetr_merged.py" \
    --tiles "$PREPARED/rfdetr_tiles/valid" \
    --original "$PREPARED/coco/valid" \
    --source-images "$REMOTE_REPO/data/train/images" \
    --checkpoint "$CHECKPOINT" \
    --output "$EVAL_DIR" \
    --batch-size 16 \
    --full-grid \
    --tile-size 704 \
    --tile-overlap 0.25 \
    --score-threshold 0.001 \
    --max-det 500 \
    --nms-iou 0.60 \
    --owner-mode owner \
    --min-area 200 \
    --wandb-run "$RUN_NAME"
