#!/bin/bash
#SBATCH --job-name=eli-yolo-select
#SBATCH --account=open-37-16
#SBATCH --partition=qcpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00

set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
RUN_ROOT="$ELI_ROOT/runs/yolo_scene_pilots"

module purge
module load Python/3.12.3-GCCcore-13.3.0
"$ELI_ROOT/venvs/yolo/bin/python" "$SOURCE_DIR/select_yolo_pilot_lr.py" \
    --pilot1 "$RUN_ROOT/pilot1/evaluation/merged_metrics.json" \
    --pilot2 "$RUN_ROOT/pilot2/evaluation/merged_metrics.json" \
    --output "$RUN_ROOT/selection.json" \
    --minimum-gain 0.005
