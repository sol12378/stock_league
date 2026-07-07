#!/usr/bin/env bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT_DIR"
python3 outputs/phase2_top1200_walkforward_fix/scripts/phase2_top1200_walkforward_fix/generate_top1200_walkforward_fix.py
