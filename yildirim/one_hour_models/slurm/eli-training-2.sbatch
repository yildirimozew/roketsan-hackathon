#!/bin/bash
#SBATCH --job-name=eli-training-2
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=02:00:00

set -euo pipefail
module purge
module load Python/3.12.3-GCCcore-13.3.0
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon/yildirim/one_hour_models
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export OMP_NUM_THREADS=8
export YOLO_CONFIG_DIR="$ELI_ROOT/runs/yolo-config"
export WANDB_ENTITY="${WANDB_ENTITY:-yildirimozew-eth-z-rich}"
export WANDB_PROJECT="${WANDB_PROJECT:-eli-training}"
export WANDB_RUN_GROUP=one-hour-pilots
export WANDB_DIR="$ELI_ROOT/runs/wandb"
export WANDB_MODE="${WANDB_MODE:-online}"
export WANDB_SILENT=true
mkdir -p "$WANDB_DIR" "$YOLO_CONFIG_DIR"
"$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/train_yolo.py" \
    --variant yolo12l \
    --data "$ELI_ROOT/prepared/yolo/dataset.yaml" \
    --output "$ELI_ROOT/runs/yolo12l" \
    --hours 1.0 --imgsz 1280 \
    --wandb-project eli-training --wandb-run eli-training-2
