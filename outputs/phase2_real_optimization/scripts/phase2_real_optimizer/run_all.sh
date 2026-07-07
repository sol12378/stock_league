#!/usr/bin/env bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT_DIR"
python3 outputs/phase2_real_optimization/scripts/phase2_real_optimizer/run_real_optimization.py
