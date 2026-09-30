#!/bin/bash
#SBATCH --job-name=eli-training-4
#SBATCH --account=infra01
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=72
#SBATCH --time=02:00:00
#SBATCH --output=/iopsstor/scratch/cscs/yildirimozew/eli-training/logs/eli-training-4-%j.out

set -euo pipefail

ELI_ROOT=/iopsstor/scratch/cscs/yildirimozew/eli-training
REMOTE_REPO=/iopsstor/scratch/cscs/yildirimozew/roketsan-hackathon/akya-day1
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"
DFINE="$ELI_ROOT/repos/D-FINE"
CONFIG="$DFINE/configs/dfine/dfine_eli_l.yml"
OUTPUT="$ELI_ROOT/runs/dfine_l"
EDF="$SOURCE_DIR/slurm/clariden-pytorch.toml"
VENV="$ELI_ROOT/venvs/dfine-gh200"

mkdir -p "$ELI_ROOT"/{cache,logs,prepared/coco,runs,venvs} "$OUTPUT"

export XDG_CACHE_HOME="$ELI_ROOT/cache"
export HF_HOME="$ELI_ROOT/cache/huggingface"
export TORCH_HOME="$ELI_ROOT/cache/torch"
export WANDB_ENTITY="${WANDB_ENTITY:-yildirimozew-eth-z-rich}"
export WANDB_PROJECT="${WANDB_PROJECT:-eli-training}"
export WANDB_RUN_GROUP=one-hour-pilots
export WANDB_NAME=eli-training-4
export WANDB_DIR="$ELI_ROOT/runs/wandb"
export WANDB_MODE=offline
export WANDB_SILENT=true
export OMP_NUM_THREADS=8
mkdir -p "$WANDB_DIR" "$HF_HOME" "$TORCH_HOME"

container_run() {
    srun --mpi=pmix --network=disable_rdzv_get --environment="$EDF" "$@"
}
SRUN_CONTAINER=(srun --mpi=pmix --network=disable_rdzv_get --environment="$EDF")

# Create a lightweight environment on the GH200 architecture and prepare only
# the original-image COCO data required by D-FINE.
container_run --ntasks=1 bash -lc "
set -euo pipefail
if [[ ! -x '$VENV/bin/python' ]]; then
    python -m venv --system-site-packages '$VENV'
fi
'$VENV/bin/python' -m pip install --disable-pip-version-check -q \
    faster-coco-eval PyYAML tensorboard scipy calflops transformers loguru wandb
'$VENV/bin/python' - <<'PY'
import sys
from pathlib import Path

repo = Path('$REMOTE_REPO')
source = Path('$SOURCE_DIR')
output = Path('$ELI_ROOT/prepared/coco')
sys.path.insert(0, str(source))
from prepare_data import read_annotations, read_ids, write_coco_split

images = repo / 'data/train/images'
annotations = read_annotations(repo / 'data/train/annotations.csv')
splits = {
    'train': read_ids(repo / 'splits/folds/fold_1_train.txt'),
    'valid': read_ids(repo / 'splits/folds/fold_1_val.txt'),
}
for split, ids in splits.items():
    write_coco_split(output, split, ids, images, annotations)
PY
sed -e 's|__DATA_ROOT__|$ELI_ROOT/prepared/coco|g' \
    -e 's|__OUTPUT_DIR__|$OUTPUT|g' \
    '$SOURCE_DIR/dfine_eli_l.yml' > '$CONFIG'
"

cd "$DFINE"
set +e
timeout --signal=TERM --kill-after=120s 3600s \
    "${SRUN_CONTAINER[@]}" --ntasks=1 bash -lc "
cd '$DFINE'
'$VENV/bin/torchrun' --standalone --nproc_per_node=4 train.py \
    -c '$CONFIG' --use-amp --seed 42 --output-dir '$OUTPUT' \
    -t '$ELI_ROOT/weights/dfine_l_coco.pth'
"
train_status=$?
set -e
if [[ $train_status -ne 0 && $train_status -ne 124 && $train_status -ne 143 ]]; then
    exit "$train_status"
fi

test -f "$OUTPUT/last.pth"
container_run --ntasks=1 bash -lc "
cd '$DFINE'
'$VENV/bin/python' train.py -c '$CONFIG' --use-amp --seed 42 \
    --output-dir '$OUTPUT/evaluation' --test-only -r '$OUTPUT/last.pth'
"
