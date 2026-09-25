#!/bin/bash
#SBATCH --job-name=eli-cv-test
#SBATCH --account=open-37-16
#SBATCH --partition=qgpu_exp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=96G
#SBATCH --time=00:10:00

set -euo pipefail
module purge
module load Python/3.12.3-GCCcore-13.3.0

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
RUN_DIR="$ELI_ROOT/runs/rfdetr_convnext_cv"
CHECKPOINT="$ELI_ROOT/runs/rfdetr_scene_a/checkpoint_best_ema.pth"
OUTPUT="$RUN_DIR/test_features"
export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export OMP_NUM_THREADS=8

test ! -e "$OUTPUT"
nms=$("$ELI_ROOT/venvs/rfdetr/bin/python" -c "import json; print(json.load(open('$RUN_DIR/calibration/calibration.json'))['nms_iou'])")
accepted=$("$ELI_ROOT/venvs/rfdetr/bin/python" -c "import json; print(int(json.load(open('$RUN_DIR/calibration/calibration.json'))['accepted']))")
classifier_args=()
if [[ "$accepted" == 1 ]]; then
    classifier_args+=(--classifier "$ELI_ROOT/runs/convnext_cv/best_ema.pt")
fi
"$ELI_ROOT/venvs/rfdetr/bin/python" "$SOURCE_DIR/rfdetr_convnext_fusion.py" extract \
    --images "$REMOTE_REPO/data/test/images" \
    --checkpoint "$CHECKPOINT" \
    "${classifier_args[@]}" \
    --output "$OUTPUT" \
    --batch-size 16 \
    --classifier-batch-size 512 \
    --nms-iou "$nms"
