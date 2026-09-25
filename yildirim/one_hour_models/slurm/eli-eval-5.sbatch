#!/bin/bash
#SBATCH --job-name=eli-eval-5
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=00:45:00

set -euo pipefail
module purge
module load Python/3.11.3-GCCcore-12.3.0 CUDA/12.1.1
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
MMDET="$ELI_ROOT/repos/mmdetection"
CONFIG="$MMDET/configs/eli/cascade_eli_convnext_t.py"
OUTPUT="$ELI_ROOT/runs/cascade_convnext_t"
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export PYTHONPATH="$MMDET${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=8
export WANDB_ENTITY="${WANDB_ENTITY:-yildirimozew-eth-z-rich}"
export WANDB_PROJECT="${WANDB_PROJECT:-eli-training}"
export WANDB_RUN_GROUP=one-hour-pilots
export WANDB_NAME=eli-training-5-eval
export WANDB_DIR="$ELI_ROOT/runs/wandb"
export WANDB_MODE="${WANDB_MODE:-online}"
export WANDB_SILENT=true
mkdir -p "$WANDB_DIR" "$OUTPUT/evaluation"

checkpoint=$(find "$OUTPUT" -maxdepth 1 -type f -name 'epoch_*.pth' -print | sort -V | tail -1)
test -n "$checkpoint"
echo "Evaluating checkpoint: $checkpoint"
cd "$MMDET"
"$ELI_ROOT/venvs/mmdet/bin/python" tools/test.py "$CONFIG" "$checkpoint" \
    --work-dir "$OUTPUT/evaluation" \
    --cfg-options vis_backends.1.init_kwargs.name=eli-training-5-eval
