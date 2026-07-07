# Environment Report

| module | status | version | path |
| --- | --- | --- | --- |
| optuna | OK | 4.9.0 | /Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/phase2_real_optimization/vendor/optuna/__init__.py |
| numpy | OK | 2.0.2 | /Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/phase2_real_optimization/vendor/numpy/__init__.py |
| pandas | OK | 2.3.3 | /Users/satouryuuichi/Library/Python/3.9/lib/python/site-packages/pandas/__init__.py |
| scipy | OK | 1.13.1 | /Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/phase2_real_optimization/vendor/scipy/__init__.py |
| sklearn | OK | 1.6.1 | /Users/satouryuuichi/Library/Python/3.9/lib/python/site-packages/sklearn/__init__.py |
| matplotlib | OK | 3.9.4 | /Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/phase2_real_optimization/vendor/matplotlib/__init__.py |
| pymoo | OK | 0.6.1.5 | /Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/phase2_real_optimization/vendor/pymoo/__init__.py |

- Optuna TPE uses `optuna.samplers.TPESampler(seed=42, multivariate=True, group=True)`.
- NSGA-II uses `optuna.samplers.NSGAIISampler(seed=43, population_size=100)`.
