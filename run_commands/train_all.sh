#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------
#  Sequential training script for Go2 terrain locomotion
#  Stage 1 -> Stage 2 (rough) -> Stage 3 (stairs)
#  Each stage automatically picks up the highest iteration checkpoint from the
#  previous stage. Logs are written under ~/isaaclab_logs/.*
# ---------------------------------------------------------------------

# Resolve the repository root (same logic as the original scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

cd "${REPO}"

# ---------------------------------------------------------------------
# Stage 1: flat‑ground prior
# ---------------------------------------------------------------------
echo "=== Training Stage 1: Flat‑ground prior ==="
bash scripts/isaaclab_user.sh -p scripts/train_flat_prior.py \
    --task Go2-Terrain-Flat-Prior-V1 \
    --log-dir ~/isaaclab_logs/go2_terrain_flat_prior_v1 \
    --headless

# Find the checkpoint with the highest numerical iteration produced by stage 1
STAGE1_CKPT=$(ls -v ~/isaaclab_logs/go2_terrain_flat_prior_v1/model_*.pt 2>/dev/null | tail -n1)
if [[ -z "$STAGE1_CKPT" ]]; then
    echo "[ERROR] No checkpoint found for Stage 1 – aborting."
    exit 1
fi

echo "Stage 1 checkpoint: $STAGE1_CKPT"

# ---------------------------------------------------------------------
# Stage 2: rough terrain (blind policy)
# ---------------------------------------------------------------------
echo "=== Training Stage 2: Rough terrain (blind) ==="
bash scripts/isaaclab_user.sh -p scripts/train_terrain_policy.py \
    --stage rough \
    --log-dir ~/isaaclab_logs/go2_terrain_locomotion_rough_v1 \
    --headless \
    --flat-prior-checkpoint "$STAGE1_CKPT"

# Locate the checkpoint with the highest numerical iteration from stage 2
STAGE2_CKPT=$(ls -v ~/isaaclab_logs/go2_terrain_locomotion_rough_v1/model_*.pt 2>/dev/null | tail -n1)
if [[ -z "$STAGE2_CKPT" ]]; then
    echo "[ERROR] No checkpoint found for Stage 2 – aborting."
    exit 1
fi

echo "Stage 2 checkpoint: $STAGE2_CKPT"

# ---------------------------------------------------------------------
# Stage 3: stairs (blind policy with stair‑specific shaping)
# ---------------------------------------------------------------------
echo "=== Training Stage 3: Stairs ==="
bash scripts/isaaclab_user.sh -p scripts/train_terrain_policy.py \
    --stage stairs \
    --log-dir ~/isaaclab_logs/go2_terrain_locomotion_stairs_v1 \
    --headless \
    --rough-checkpoint "$STAGE2_CKPT"

echo "All stages completed successfully."