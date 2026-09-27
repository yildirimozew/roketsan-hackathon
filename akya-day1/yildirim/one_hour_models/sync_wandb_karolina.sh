#!/bin/bash
set -euo pipefail

ELI_ROOT=/mnt/proj1/open-37-16/yildirimozew/eli-training
RUN_ROOT="$ELI_ROOT/runs"
PYTHON="$ELI_ROOT/venvs/rfdetr/bin/python"

if [[ "$(hostname -f)" != login*.karolina.it4i.cz ]]; then
    echo "Run this command on a Karolina login node; compute nodes cannot reliably reach W&B." >&2
    exit 2
fi

module purge >/dev/null 2>&1
module load Python/3.12.3-GCCcore-13.3.0
source "$(dirname "$0")/wandb_karolina.env"
export WANDB_MODE=online

"$PYTHON" - <<'PY'
import wandb

if not wandb.login(verify=True, relogin=False):
    raise SystemExit("W&B authentication verification failed")
print("W&B authentication verified")
PY

if (( $# )); then
    run_dirs=("$@")
else
    mapfile -d '' run_dirs < <(find "$RUN_ROOT" -type d -name 'offline-run-*' -print0)
fi

pending=()
for run_dir in "${run_dirs[@]}"; do
    [[ -d "$run_dir" ]] || continue
    run_file=$(find "$run_dir" -maxdepth 1 -type f -name 'run-*.wandb' -print -quit)
    [[ -n "$run_file" ]] || continue
    [[ -e "$run_file.synced" ]] && continue
    [[ -e "$run_dir/.skip-sync" ]] && continue
    # Active runs update this record continuously. Do not upload until quiet.
    if find "$run_file" -mmin -5 -print -quit | grep -q .; then
        echo "Skipping active/recent run: $run_dir"
        continue
    fi
    pending+=("$run_dir")
done

if (( ${#pending[@]} == 0 )); then
    echo "No completed unsynced offline runs found."
    exit 0
fi

"$PYTHON" -m wandb sync \
    --entity "$WANDB_ENTITY" \
    --project "$WANDB_PROJECT" \
    --skip-synced \
    "${pending[@]}"
