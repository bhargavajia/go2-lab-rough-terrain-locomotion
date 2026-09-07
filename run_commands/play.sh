#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

usage() {
 cat <<'EOF'
Usage:
 play.sh [--bundle-name name] [--task task]
 play.sh /path/to/exported/bundle
EOF
}

BUNDLE_NAME="go2_candidate_bundle"
TASK_NAME="Go2-Terrain-Locomotion-Stairs-Eval-V1"
BUNDLE_DIR=""

while [[ $# -gt 0 ]]; do
 case "$1" in
   --bundle-name)
     BUNDLE_NAME="${2:-}"
     shift 2
     ;;
   --bundle-name=*)
     BUNDLE_NAME="${1#*=}"
     shift
     ;;
   --task)
     TASK_NAME="${2:-}"
     shift 2
     ;;
   --task=*)
     TASK_NAME="${1#*=}"
     shift
     ;;
   -h|--help)
     usage
     exit 0
     ;;
   --)
     shift
     if [[ $# -gt 0 ]]; then
       BUNDLE_DIR="$(realpath "$1")"
     fi
     break
     ;;
   -*)
     echo "Unknown option: $1"
     usage
     exit 1
     ;;
   *)
     if [[ -z "${BUNDLE_DIR}" ]]; then
       if [[ -d "$1" ]]; then
         BUNDLE_DIR="$(realpath "$1")"
       else
         BUNDLE_NAME="$1"
       fi
     fi
     shift
     ;;
 esac
done

if [[ -z "${BUNDLE_DIR}" ]]; then
 BUNDLE_DIR="${REPO}/artifacts/exported/${BUNDLE_NAME}"
fi

echo "=================================================="
echo " Playing Exported Policy in GUI Simulation"
echo " Bundle Dir: ${BUNDLE_DIR}"
echo " Task:       ${TASK_NAME}"
echo "=================================================="

cd "${REPO}"

exec bash scripts/isaaclab_user.sh -p scripts/deploy/play_deploy_policy.py \
  --bundle-dir "${BUNDLE_DIR}" \
  --task "${TASK_NAME}" \
  --num-envs 4 \
  "$@"
