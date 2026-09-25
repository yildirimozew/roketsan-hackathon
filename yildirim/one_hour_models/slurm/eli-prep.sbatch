#!/bin/bash
#SBATCH --job-name=eli-prep
#SBATCH --account=open-37-16
#SBATCH --partition=qcpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=04:00:00

set -euo pipefail

REMOTE_REPO=/mnt/proj1/open-37-16/yildirimozew/roketsan-hackathon
ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
SOURCE_DIR="$REMOTE_REPO/yildirim/one_hour_models"

mkdir -p "$ELI_ROOT"/{logs,repos,runs,venvs,weights}

module purge
module load Python/3.12.3-GCCcore-13.3.0

create_venv() {
    local path=$1
    if [[ ! -x "$path/bin/python" ]]; then
        python -m venv "$path"
    fi
    "$path/bin/python" -m pip install --upgrade pip setuptools wheel
}

create_system_venv() {
    local path=$1
    if [[ ! -x "$path/bin/python" ]]; then
        python -m venv --system-site-packages "$path"
    fi
    "$path/bin/python" -m pip install --upgrade pip setuptools wheel
}

create_venv "$ELI_ROOT/venvs/common"
"$ELI_ROOT/venvs/common/bin/pip" install \
    torch==2.6.0 torchvision==0.21.0 \
    --index-url https://download.pytorch.org/whl/cu124
"$ELI_ROOT/venvs/common/bin/pip" install ultralytics==8.4.163 wandb

if [[ ! -d "$ELI_ROOT/repos/rf-detr/.git" ]]; then
    git clone https://github.com/roboflow/rf-detr.git "$ELI_ROOT/repos/rf-detr"
fi
git -C "$ELI_ROOT/repos/rf-detr" fetch --depth=1 origin
git -C "$ELI_ROOT/repos/rf-detr" checkout --detach FETCH_HEAD
"$ELI_ROOT/venvs/common/bin/pip" install -e "$ELI_ROOT/repos/rf-detr[train,loggers]" wandb

if [[ ! -d "$ELI_ROOT/repos/D-FINE/.git" ]]; then
    git clone https://github.com/Peterande/D-FINE.git "$ELI_ROOT/repos/D-FINE"
fi
git -C "$ELI_ROOT/repos/D-FINE" fetch --depth=1 origin
git -C "$ELI_ROOT/repos/D-FINE" checkout --detach FETCH_HEAD
"$ELI_ROOT/venvs/common/bin/pip" install -r "$ELI_ROOT/repos/D-FINE/requirements.txt" wandb

for alias in yolo rfdetr dfine; do
    alias_path="$ELI_ROOT/venvs/$alias"
    if [[ -d "$alias_path" && ! -L "$alias_path" ]]; then
        mv "$alias_path" "$alias_path.pre-common-$(date +%s)"
    fi
    ln -sfn common "$alias_path"
done

python "$SOURCE_DIR/prepare_data.py" \
    --repo "$REMOTE_REPO" \
    --output "$ELI_ROOT/prepared"
python "$SOURCE_DIR/check_prepared.py" --prepared "$ELI_ROOT/prepared"

sed \
    -e "s|__DATA_ROOT__|$ELI_ROOT/prepared/coco|g" \
    -e "s|__OUTPUT_DIR__|$ELI_ROOT/runs/dfine_l|g" \
    "$SOURCE_DIR/dfine_eli_l.yml" \
    > "$ELI_ROOT/repos/D-FINE/configs/dfine/dfine_eli_l.yml"

curl -L --fail --retry 3 \
    -o "$ELI_ROOT/weights/dfine_l_coco.pth" \
    https://github.com/Peterande/storage/releases/download/dfinev1.0/dfine_l_coco.pth

"$ELI_ROOT/venvs/yolo/bin/python" - <<'PY'
from ultralytics import YOLO
YOLO("yolo26s.pt")
YOLO("yolo12l.pt")
PY

module purge
module load PyTorch/2.1.2-foss-2023a-CUDA-12.1.1
if [[ ! -d "$ELI_ROOT/repos/mmdetection/.git" ]]; then
    git clone --branch v3.3.0 --depth 1 https://github.com/open-mmlab/mmdetection.git "$ELI_ROOT/repos/mmdetection"
fi
git -C "$ELI_ROOT/repos/mmdetection" checkout --detach v3.3.0
create_system_venv "$ELI_ROOT/venvs/mmdet"
"$ELI_ROOT/venvs/mmdet/bin/pip" install openmim mmpretrain
"$ELI_ROOT/venvs/mmdet/bin/mim" install 'mmcv==2.1.0'
"$ELI_ROOT/venvs/mmdet/bin/pip" install -v -e "$ELI_ROOT/repos/mmdetection"
"$ELI_ROOT/venvs/mmdet/bin/pip" install wandb
mkdir -p "$ELI_ROOT/repos/mmdetection/configs/eli"
sed \
    -e "s|__DATA_ROOT__|$ELI_ROOT/prepared/coco|g" \
    -e "s|__OUTPUT_DIR__|$ELI_ROOT/runs/cascade_convnext_t|g" \
    "$SOURCE_DIR/cascade_eli_convnext_t.py" \
    > "$ELI_ROOT/repos/mmdetection/configs/eli/cascade_eli_convnext_t.py"

curl -L --fail --retry 3 \
    -o "$ELI_ROOT/weights/cascade_convnext_t_coco.pth" \
    https://download.openmmlab.com/mmdetection/v2.0/convnext/cascade_mask_rcnn_convnext-t_p4_w7_fpn_giou_4conv1f_fp16_ms-crop_3x_coco/cascade_mask_rcnn_convnext-t_p4_w7_fpn_giou_4conv1f_fp16_ms-crop_3x_coco_20220509_204200-8f07c40b.pth
sed -i \
    "s|load_from = 'https://[^']*'|load_from = '$ELI_ROOT/weights/cascade_convnext_t_coco.pth'|" \
    "$ELI_ROOT/repos/mmdetection/configs/eli/cascade_eli_convnext_t.py"

{
    echo "prepared_at=$(date --iso-8601=seconds)"
    echo "rf_detr_commit=$(git -C "$ELI_ROOT/repos/rf-detr" rev-parse HEAD)"
    echo "dfine_commit=$(git -C "$ELI_ROOT/repos/D-FINE" rev-parse HEAD)"
    echo "mmdetection_commit=$(git -C "$ELI_ROOT/repos/mmdetection" rev-parse HEAD)"
    "$ELI_ROOT/venvs/yolo/bin/pip" freeze | sed 's/^/yolo:/'
} > "$ELI_ROOT/PREPARED"
