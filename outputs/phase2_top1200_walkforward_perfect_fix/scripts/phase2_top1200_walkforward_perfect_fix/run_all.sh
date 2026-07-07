#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
.venv/bin/python scripts/phase2_top1200_walkforward_perfect_fix/generate_perfect_walkforward_panel.py
