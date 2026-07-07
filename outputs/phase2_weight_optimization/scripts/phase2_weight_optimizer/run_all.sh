#!/usr/bin/env bash
set +e
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT_DIR" || exit 1
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"
python -m scripts.phase2_weight_optimizer.load_inputs
python -m scripts.phase2_weight_optimizer.normalize_metrics
python -m scripts.phase2_weight_optimizer.random_search
python -m scripts.phase2_weight_optimizer.optuna_tpe
python -m scripts.phase2_weight_optimizer.nsga2
python -m scripts.phase2_weight_optimizer.validation
python -m scripts.phase2_weight_optimizer.ablation
python -m scripts.phase2_weight_optimizer.reporting
exit 0
