#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

cd "${REPO}"

exec bash scripts/isaaclab_user.sh -p scripts/train_flat_prior.py \
  --task Go2-Terrain-Flat-Prior-V1 \
  --log-dir ~/isaaclab_logs/go2_terrain_flat_prior_v1 \
  --headless \
  "$@"
