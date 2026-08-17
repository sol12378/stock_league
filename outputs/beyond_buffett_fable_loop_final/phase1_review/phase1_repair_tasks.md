# Phase1 Repair Tasks（loop 1）

スコア 96/100（PASS）のため再構築は不要。以下は説明品質を高めるための修復タスクで、担当 Phase を明記する。

| ID | タスク | 重要度 | 対応先 | 状態 |
|---|---|---|---|---|
| R1-1 | Top5 と sector-adjusted final20 の rank 非連続（rank3=9990, rank4=8278 のスキップ）を「同一業種原則2社まで」制約として一元的に説明 | 中 | explain_docs/phase1_explanation_material.md（本ループ） | **本ループで対応済み** |
| R1-2 | Piotroski 6/9 available 版・Ohlson/Altman 原式未実装（simple distress guardrail 代替）を最終レポート III 章「限界」に明記 | 中 | Phase7 final_report.md | Phase7 で対応 |
| R1-3 | 6430 配当データ乖離・current-data look-ahead bias の脚注転記 | 低 | Phase7 final_report.md | Phase7 で対応 |
| R1-4 | GP の小売（Retail Trade）バイアス（Top5 上位2社が小売）を「業種2社上限」guardrail とセットで説明 | 中 | explain_docs/phase1_explanation_material.md | **本ループで対応済み** |

## 修復しないと決めた事項（理由つき）

- **Ohlson/Altman を今から実装すること**：入力変数（GNP price-level index、working capital 等）が入手不能で、無理な proxy 実装はかえって「先行研究式の忠実な適用」という Phase1 の性格を損なう。未実装の開示＋simple guardrail 代替が学術的に誠実。
- **Piotroski を 9/9 に拡張すること**：同上。available ratio 方式（≥0.65）は欠損を透明に扱う設計としてすでに文書化されている。
