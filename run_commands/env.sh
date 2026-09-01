#!/usr/bin/env bash
# Environment setup for Go2 Rough Terrain Locomotion

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Dynamic Repository Root
export REPO="$(cd "${SCRIPT_DIR}/.." && pwd)"

# System & Tooling Paths
export ISAACLAB_ROOT="${ISAACLAB_ROOT:-/opt/IsaacLab}"
export GO2_ETH_IF="${GO2_ETH_IF:-eth0}"
export MUJOCO_PYTHON="${MUJOCO_PYTHON:-python}"

# Fix CUDA libcusparseLt library path for Isaac Sim PyTorch
ML_ARCHIVE="${ISAACLAB_ROOT}/_isaac_sim/exts/omni.isaac.ml_archive/pip_prebundle"
if [[ -d "${ML_ARCHIVE}" ]]; then
    ML_LIB_PATHS="$(find "${ML_ARCHIVE}" -path '*/lib' -type d 2>/dev/null | paste -sd: -)"
    if [[ -n "${ML_LIB_PATHS}" ]]; then
        export LD_LIBRARY_PATH="${ML_LIB_PATHS}:${LD_LIBRARY_PATH:-}"
    fi
fi

# Isaac Sim Robot USD Asset (Bundled in repo)
export GO2_USD_PATH="${REPO}/assets/robots/go2/go2.usd"

# Export Bundles & External Dependencies
export TERRAIN_BUNDLE="${TERRAIN_BUNDLE:-${REPO}/artifacts/exported/go2_terrain_locomotion_steps_v1_candidate}"
export UNITREE_SDK2PY_ROOT="${UNITREE_SDK2PY_ROOT:-${REPO}/third_party/unitree_sdk2py}"
export GO2_MUJOCO_MODEL="${GO2_MUJOCO_MODEL:-}"

echo "=================================================="
echo " Go2 Environment Variables Loaded"
echo " REPO:                ${REPO}"
echo " ISAACLAB_ROOT:       ${ISAACLAB_ROOT}"
echo " GO2_USD_PATH:        ${GO2_USD_PATH}"
echo " TERRAIN_BUNDLE:      ${TERRAIN_BUNDLE}"
echo "=================================================="
