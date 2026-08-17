#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
export PHASE3_REPO_ROOT="${REPO_ROOT}"

python3 "${SCRIPT_DIR}/phase3_v2_pipeline.py"
