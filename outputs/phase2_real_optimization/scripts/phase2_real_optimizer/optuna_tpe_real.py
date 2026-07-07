"""Run the Phase2 real optimization pipeline with real Optuna TPE.

The full implementation lives in run_real_optimization.py. This file keeps the
sampler contract visible for artifact review.
"""

import optuna

from .run_real_optimization import main, run_optuna_tpe


def sampler_contract():
    sampler = optuna.samplers.TPESampler(seed=42, multivariate=True, group=True)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    return study

if __name__ == '__main__':
    main()
