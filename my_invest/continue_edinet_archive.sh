#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")" && pwd)"
python_bin="/Users/satouryuuichi/Desktop/product/hobby/stock_league/.venv/bin/python"
archive_program="$project_dir/edinet_full_archive.py"

# Research value per byte first; every advertised payload type remains in scope.
# Each command is idempotent and resumes from the SQLite manifest.
for payload_type in 4 5 1 3 2; do
  "$python_bin" "$archive_program" \
    --interval 0.25 \
    download \
    --types "$payload_type" \
    --reserve-gib 60
done

"$python_bin" "$archive_program" reconcile
"$python_bin" "$archive_program" audit
