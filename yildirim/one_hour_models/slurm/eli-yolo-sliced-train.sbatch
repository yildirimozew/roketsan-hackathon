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

if [[ "${PILOT:-}" != "1" && "${PILOT:-}" != "2" && "${PILOT:-}" != "3" ]]; then
    echo "PILOT must be 1, 2, or 3" >&2
    exit 2
fi

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
PREPARED="$ELI_ROOT/prepared/yolo_scene_pilots"
RUN_ROOT="$ELI_ROOT/runs/yolo_scene_pilots"
RUN_DIR="$RUN_ROOT/pilot$PILOT"
RUN_NAME="yolo26-sliced-pilot-$PILOT-train"

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
export ELI_GIT_COMMIT="${ELI_GIT_COMMIT:-unknown}"
mkdir -p "$WANDB_DIR" "$RUN_DIR"

"$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/check_yolo_sliced.py" \
    --prepared "$PREPARED" --repo "$REMOTE_REPO"

if [[ "$PILOT" == "1" ]]; then
    LR0=0.001
    RATIO=0.25
    DATA="$PREPARED/dataset_ratio25.yaml"
elif [[ "$PILOT" == "2" ]]; then
    LR0=0.0005
    RATIO=0.25
    DATA="$PREPARED/dataset_ratio25.yaml"
else
    SELECTION="$RUN_ROOT/selection.json"
    test -f "$SELECTION"
    LR0=$("$ELI_ROOT/venvs/yolo/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["selected_lr0"])' "$SELECTION")
    RATIO=0.40
    DATA="$PREPARED/dataset_ratio40.yaml"
fi

"$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/train_yolo_sliced.py" \
    --data "$DATA" \
    --output "$RUN_DIR" \
    --pilot "$PILOT" \
    --lr0 "$LR0" \
    --centered-ratio "$RATIO" \
    --minutes 48 \
    --epochs 40 \
    --wandb-project eli-training \
    --wandb-run "$RUN_NAME"
