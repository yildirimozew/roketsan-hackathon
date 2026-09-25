#!/bin/bash
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=64G
#SBATCH --time=00:25:00

set -euo pipefail

if [[ "${PILOT:-}" != "1" && "${PILOT:-}" != "2" && "${PILOT:-}" != "3" ]]; then
    echo "PILOT must be 1, 2, or 3" >&2
    exit 2
fi

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
PREPARED="$ELI_ROOT/prepared/yolo_scene_pilots"
RUN_DIR="$ELI_ROOT/runs/yolo_scene_pilots/pilot$PILOT"
RUN_NAME="yolo26-sliced-pilot-$PILOT-eval"

module purge
module load Python/3.12.3-GCCcore-13.3.0
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export YOLO_CONFIG_DIR="$ELI_ROOT/runs/yolo-config"
export OMP_NUM_THREADS=8
source "$SOURCE_DIR/wandb_karolina.env"
export WANDB_RUN_GROUP=yolo26-sliced-pilots
export WANDB_DIR="$ELI_ROOT/runs/wandb/$RUN_NAME"
mkdir -p "$WANDB_DIR" "$RUN_DIR/evaluation"

"$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/evaluate_yolo_sliced.py" \
    --repo "$REMOTE_REPO" \
    --original "$PREPARED/validation/images/val" \
    --source-images "$REMOTE_REPO/data/train/images" \
    --weights "$REMOTE_REPO/splits/scene_holdout_v2/val_strata.csv" \
    --checkpoint "$RUN_DIR/train/weights/last.pt" \
    --output "$RUN_DIR/evaluation" \
    --batch-size 32 \
    --tile-size 704 \
    --tile-overlap 0.25 \
    --score-threshold 0.001 \
    --max-det 500 \
    --nms-iou 0.50 0.55 0.60 0.65 0.70 \
    --min-area 200 \
    --wandb-run "$RUN_NAME"
