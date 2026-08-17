#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
.venv/bin/python scripts/phase2_perfect_final_break/generate_phase2_perfect_final_break.py
