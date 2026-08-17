# Source Hierarchy（正典階層）

本プロジェクト「BEYOND BUFFETT」最終ループにおいて、複数世代の成果物のうち **どれを正（canonical）とするか** を以下に確定する。

## 確定事項

| 領域 | 正とする成果物 | 参照群・旧版 |
|---|---|---|
| Phase1 Buffett Core Top5 | `outputs/phase1_top5/phase1_buffett_core_top5.csv` および同フォルダのレポート群 | `phase1_final`, `phase1_buffett_complete`, `phase1_repair` は過程資産（監査時のみ参照） |
| Phase2 正式母集団 | `outputs/phase2_perfect_final_break/formal_top1200/phase2_formal_top1200_candidates.csv`（**formal_top1200 が正式母集団**） | `phase2_formal_top100.csv` / `phase2_formal_top300.csv` は優先度レイヤ、`phase2_top2000_reference.csv` は**参照群**（母集団ではない） |
| Phase2 最適化解 | `outputs/phase2_perfect_final_break/optimization/selected_phase2_solution_clean.json` | 旧 `phase2_real_optimization`, `phase2_weight_optimization` 等は探索過程 |
| Phase3 スコアリング・Final20 | `outputs/phase3_beyond_buffett_v2/`（**v2 を正**） | `outputs/phase3_beyond_buffett/`（v1）は差分監査用に保持。v1→v2差分は `phase3_v1_to_v2_selection_diff.md` で監査済み |
| 価格データ | `data/processed/prices_daily.parquet`（3,650銘柄、2021-06〜、^N225・1306.T含む） | `data/raw/prices/` は空（rawは使わない） |
| 論文書式 | `docs/2026年度募集要項.docx` | — |
| 式スタイル | `docs/explain_docs/phase1_buffett_methodology_report_flow_v2.tex`, `phase2_methodology_report_polished.tex` | `docs/outliers*` は未発見のため、explain_docs の式セクション様式を代替スタイル正典とする |

## 原則

1. **Phase1 Top5 は固定**：Final20 の Buffett Core として不変。Phase3 側の再スコアで入れ替えない。
2. **Phase2 formal_top1200 が Phase3 の唯一の母集団**：Top2000 は感度確認のための参照群であり、選定には使わない。
3. **Phase2 スコア（final_exploratory_weighted_score / phase2 rank）は最終選定スコアではない**：Phase3 の Transformation / Emerging スコアが選定を駆動し、Phase2 側は confidence・guardrail 情報としてのみ使う。
4. **Phase3 は v2 優先**：v1 は監査証跡。両者の差分が説明不能な場合は本ループの review で指摘・修正する。
5. 本ループの成果物は `outputs/beyond_buffett_fable_loop_final/` に**追加のみ**で作成し、既存成果物は削除・改変しない。

## 世代の整理（なぜ複数世代が存在するか)

- phase2_weight_optimization → phase2_real_optimization → phase2_top1200_walkforward_fix → phase2_top1200_walkforward_perfect_fix → phase2_final_integrated_break → **phase2_perfect_final_break（最終）** の順に修復・統合されてきた。
- 最終世代のみが normalization consensus・walk-forward 検証・flag 監査を完備しているため、これを正とする。
