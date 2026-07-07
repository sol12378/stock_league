#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
.venv/bin/python scripts/phase2_final_integrated_break/generate_phase2_final_integrated_break.py
