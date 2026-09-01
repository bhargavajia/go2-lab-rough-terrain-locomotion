#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

cd "${REPO}"

CKPT_ARGS=()
if [[ -n "${1:-}" ]]; then
  CKPT_ARGS=(--rough-checkpoint "$1")
fi

exec bash scripts/isaaclab_user.sh -p scripts/train_terrain_policy.py \
  --stage stairs \
  --log-dir ~/isaaclab_logs/go2_terrain_locomotion_stairs_v1 \
  --headless \
  "${CKPT_ARGS[@]}"
