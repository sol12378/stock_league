# Phase1 vs Weighted Experiment Report

This report compares the strict Phase1 Top5 and candidate pool with exploratory weighted rankings. The weighted score is not an official Phase1 formula.

| group | count | phase1_top5_overlap | bm_median | ep_median | gp_median | piotroski_median | distress_rate | anomaly_rate | sector_hhi |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phase1 strict Top5 | 5 | 5 | 1.4416281315483317 | 0.2040707732159516 | 0.4661222776211255 | 1.0 | 0.0 | 0.0 | 0.28 |
| Phase1 candidate pool | 33 | 5 | 1.506854345955597 | 0.1222739202966637 | 0.3105174030058363 | 0.8333333333333334 | 0.0 | 0.0 | 0.11478420569329664 |
| Weighted Top50 | 50 | 3 | 1.440916090202303 | 0.1774698838194121 | 0.30901204383630926 | 1.0 | 0.0 | 0.0 | 0.092 |
| Weighted Top100 | 100 | 4 | 1.427323545646951 | 0.1492082270801946 | 0.3183233608648727 | 1.0 | 0.0 | 0.0 | 0.07860000000000003 |
| Weighted Top300 | 300 | 5 | 1.2562121064190146 | 0.11772493475709406 | 0.333054301827232 | 0.8333333333333334 | 0.0 | 0.0 | 0.08542222222222223 |
| Weighted Top1000 | 1000 | 5 | 1.0493248226897331 | 0.096450026656984 | 0.30617349287464013 | 0.8333333333333334 | 0.0 | 0.002 | 0.07537799999999999 |

## Interpretation
Phase1 emphasizes transparent sequential screening. The weighted experiment emphasizes continuous sensitivity across value, quality, safety, liquidity, and penalties. Overlap should be read as robustness evidence, not as replacement logic.
