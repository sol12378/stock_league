# Input Inventory（入力資産棚卸し）

生成日時: 2026-07-10

| キー | パス | 存在 | ファイル数 | 総サイズ(MB) | 最終更新 |
|---|---|---|---|---|---|
| phase1_top5 | outputs/phase1_top5 | YES | 22 | 2.2 | 2026-07-07 23:32 |
| phase1_final | outputs/phase1_final | YES | 45 | 7.6 | 2026-07-07 16:18 |
| phase1_buffett_complete | outputs/phase1_buffett_complete | YES | 36 | 3.8 | 2026-07-07 22:38 |
| phase1_repair | outputs/phase1_repair | YES | 19 | 5.3 | 2026-07-07 15:53 |
| phase2_perfect_final_break | outputs/phase2_perfect_final_break | YES | 74 | 89.0 | 2026-07-08 11:01 |
| phase2_final_integrated_break | outputs/phase2_final_integrated_break | YES | 60 | 88.2 | 2026-07-08 09:31 |
| phase2_real_optimization | outputs/phase2_real_optimization | YES | 73 | 119.1 | 2026-07-08 00:59 |
| phase2_top1200_walkforward_fix | outputs/phase2_top1200_walkforward_fix | YES | 52 | 12.7 | 2026-07-08 01:28 |
| phase2_top1200_walkforward_perfect_fix | outputs/phase2_top1200_walkforward_perfect_fix | YES | 32 | 171.6 | 2026-07-08 02:07 |
| phase2_weight_optimization | outputs/phase2_weight_optimization | YES | 59 | 4.1 | 2026-07-08 00:23 |
| phase3_v1 | outputs/phase3_beyond_buffett | YES | 64 | 27.7 | 2026-07-10 13:49 |
| phase3_v2 | outputs/phase3_beyond_buffett_v2 | YES | 87 | 31.5 | 2026-07-10 15:40 |
| work_phase2 | work/phase2_perfect_final_break | YES | 73 | 89.0 | 2026-07-10 15:40 |
| work_phase3_v1 | work/phase3_beyond_buffett_v1 | YES | 64 | 27.7 | 2026-07-10 13:49 |
| docs | docs | YES | 28 | 54.3 | 2026-07-10 19:11 |
| docs_explain | docs/explain_docs | YES | 9 | 2.4 | 2026-07-10 19:11 |
| data | data | YES | 12048 | 17041.5 | 2026-06-23 01:05 |
| submission_assets | submission_assets | YES | 139 | 25.6 | 2026-07-06 18:24 |

## 主要単体ファイル

| パス | 存在 | サイズ(KB) |
|---|---|---|
| docs/2026年度募集要項.docx | YES | 1409 |
| phase1_buffett_complete.zip | YES | 921 |
| phase1_top5.zip | YES | 584 |
| outputs/phase2_perfect_final_break.zip | YES | 13036 |
| outputs/phase3_beyond_buffett.zip | YES | 6863 |
| outputs/phase3_beyond_buffett_v2.zip | YES | 7479 |
| docs/explain_docs/phase1_buffett_methodology_report_flow_v2.tex | YES | 60 |
| docs/explain_docs/phase2_methodology_report_polished.tex | YES | 43 |
| docs/phase2_references.md | YES | 12 |
| docs/phase1_codex_prompt_and_formula_references.md | YES | 45 |
| docs/beyond_buffett_screening_portfolio_execution_plan.md | YES | 25 |
| docs/beyond_buffett_codex_automation_plan.md | YES | 38 |

## 注記

- `phase2_perfect_final_break(1).zip` という名称のzipは存在しないが、同一内容の `outputs/phase2_perfect_final_break.zip`（展開済みフォルダあり）が存在し、これを正とする。
- phase3はv1（outputs/phase3_beyond_buffett）とv2（outputs/phase3_beyond_buffett_v2）の両方が展開済み。v2を正とする。
- `docs/outliers*` は本ターン時点の探索では未発見（別エージェントで再探索中）。見つからない場合はmissing_inputsに記録し、代替として explain_docs のtexレポート様式を採用する。
