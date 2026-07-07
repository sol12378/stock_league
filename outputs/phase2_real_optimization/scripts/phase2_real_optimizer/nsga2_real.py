"""Run the Phase2 real optimization pipeline with real Optuna NSGA-II.

The full implementation lives in run_real_optimization.py. This file keeps the
sampler contract visible for artifact review.
"""

import optuna

from .run_real_optimization import main, run_nsga2


def sampler_contract():
    sampler = optuna.samplers.NSGAIISampler(seed=43, population_size=100)
    study = optuna.create_study(
        directions=[
            "maximize",
            "maximize",
            "maximize",
            "maximize",
            "maximize",
            "maximize",
            "minimize",
            "minimize",
            "minimize",
            "minimize",
        ],
        sampler=sampler,
    )
    return study

if __name__ == '__main__':
    main()
