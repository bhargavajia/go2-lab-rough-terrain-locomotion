#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

usage() {
  cat <<'EOF'
Usage:
  export.sh --checkpoint /path/to/checkpoint.pt [--bundle-name name] [--task task] [--phase phase]
  export.sh /path/to/checkpoint.pt [task_name] [phase_name] [bundle_name]
EOF
}

CKPT_PATH=""
BUNDLE_NAME="go2_candidate_bundle"
TASK_NAME="Go2-Terrain-Locomotion-Stairs-V1"
PHASE_NAME="terrain-locomotion-stairs-v1"
CKPT_SET=false
TASK_SET=false
PHASE_SET=false
BUNDLE_SET=false
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --checkpoint)
      CKPT_PATH="${2:-}"
      CKPT_SET=true
      shift 2
      ;;
    --checkpoint=*)
      CKPT_PATH="${1#*=}"
      CKPT_SET=true
      shift
      ;;
    --bundle-name)
      BUNDLE_NAME="${2:-}"
      BUNDLE_SET=true
      shift 2
      ;;
    --bundle-name=*)
      BUNDLE_NAME="${1#*=}"
      BUNDLE_SET=true
      shift
      ;;
    --task)
      TASK_NAME="${2:-}"
      TASK_SET=true
      shift 2
      ;;
    --task=*)
      TASK_NAME="${1#*=}"
      TASK_SET=true
      shift
      ;;
    --phase)
      PHASE_NAME="${2:-}"
      PHASE_SET=true
      shift 2
      ;;
    --phase=*)
      PHASE_NAME="${1#*=}"
      PHASE_SET=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      POSITIONAL+=("$@")
      break
      ;;
    -*)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

POSITIONAL_INDEX=0
if [[ -z "${CKPT_PATH}" && ${#POSITIONAL[@]} -gt 0 ]]; then
  CKPT_PATH="${POSITIONAL[0]}"
  CKPT_SET=true
  POSITIONAL_INDEX=1
fi
if [[ "${TASK_SET}" == false && ${POSITIONAL_INDEX} -lt ${#POSITIONAL[@]} ]]; then
  TASK_NAME="${POSITIONAL[${POSITIONAL_INDEX}]}"
  TASK_SET=true
  POSITIONAL_INDEX=$((POSITIONAL_INDEX + 1))
fi
if [[ "${PHASE_SET}" == false && ${POSITIONAL_INDEX} -lt ${#POSITIONAL[@]} ]]; then
  PHASE_NAME="${POSITIONAL[${POSITIONAL_INDEX}]}"
  PHASE_SET=true
  POSITIONAL_INDEX=$((POSITIONAL_INDEX + 1))
fi
if [[ "${BUNDLE_SET}" == false && ${POSITIONAL_INDEX} -lt ${#POSITIONAL[@]} ]]; then
  BUNDLE_NAME="${POSITIONAL[${POSITIONAL_INDEX}]}"
  BUNDLE_SET=true
fi

if [[ "${CKPT_SET}" == false ]]; then
  usage
  exit 1
fi

CKPT_PATH="$(realpath "${CKPT_PATH}")"
BUNDLE_DIR="${REPO}/artifacts/exported/${BUNDLE_NAME}"

echo "=================================================="
echo " Exporting Policy"
echo " Checkpoint: ${CKPT_PATH}"
echo " Task:       ${TASK_NAME}"
echo " Phase:      ${PHASE_NAME}"
echo " Bundle Dir: ${BUNDLE_DIR}"
echo "=================================================="

cd "${REPO}"

exec bash scripts/isaaclab_user.sh -p scripts/deploy/export_policy.py \
  --policy-name "${BUNDLE_NAME}" \
  --checkpoint "${CKPT_PATH}" \
  --task "${TASK_NAME}" \
  --phase "${PHASE_NAME}" \
  --bundle-dir "${BUNDLE_DIR}" \
  --policy-kind blind_history_policy \
  --observation-groups policy,policy_history \
  --policy-history-length 100 \
  --format torchscript \
  --format onnx
