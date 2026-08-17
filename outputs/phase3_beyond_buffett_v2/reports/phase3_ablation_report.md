# Ablation Report

    v2 recalculates overlap using normalized string codes, so the v1 all-zero overlap bug is removed. The variants are structural checks, not return-driven replacement rules.

    | variant | description | selected_count | overlap_with_final20 | jaccard_with_final20 | interpretation |
|---|---|---|---|---|---|
| A1 | Transformation Score only | 20 | 12 | 0.4286 | Constraint materially changes composition. |
| A2 | Emerging Score only | 20 | 16 | 0.6667 | Constraint materially changes composition. |
| A3 | Evidence Level disabled | 20 | 13 | 0.4815 | Constraint materially changes composition. |
| A4 | Value Trap Penalty disabled | 20 | 16 | 0.6667 | Constraint materially changes composition. |
| A5 | Theme Hype Penalty disabled | 20 | 13 | 0.4815 | Constraint materially changes composition. |
| A6 | Phase2 Confidence disabled | 20 | 15 | 0.6 | Constraint materially changes composition. |
| A7 | sector cap removed | 20 | 13 | 0.4815 | Constraint materially changes composition. |
| A8 | Top100 only | 20 | 7 | 0.2121 | Constraint materially changes composition. |
| A9 | Top300 only | 20 | 12 | 0.4286 | Constraint materially changes composition. |
| A10 | Top1200 all | 20 | 15 | 0.6 | Constraint materially changes composition. |
| A11 | Buffett Core not fixed | 20 | 11 | 0.3793 | Constraint materially changes composition. |
| A12 | Dual Moat slots zero | 20 | 16 | 0.6667 | Constraint materially changes composition. |
| A13 | Bridge slots zero | 20 | 16 | 0.6667 | Constraint materially changes composition. |
| A14 | Emerging Evidence Level >=2 disabled | 20 | 15 | 0.6 | Constraint materially changes composition. |
| A15 | Transformation Reform Evidence disabled | 20 | 15 | 0.6 | Constraint materially changes composition. |
