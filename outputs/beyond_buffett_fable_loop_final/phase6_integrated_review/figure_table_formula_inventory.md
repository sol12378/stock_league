# Phase6 図表・数式インベントリ

最終論文に載せる図・表・式の在庫と所在。すべてモノクロ判読対応（要項 §5）。番号は章ごとの通し（図表 I-1 …）。

## 1. 図（figures/）

| 論文番号 | ファイル | 内容 | 状態 |
|---|---|---|---|
| 図表 I-1 | explain_docs/*_flow_diagram.mmd を統合作図 | 研究全体の流れ（守破離） | mermaid→要ラスタライズ（Phase7） |
| 図表 III-1 | explain_docs/phase1_flow_diagram.mmd | Phase1 スクリーニング手順（3099→5社） | mmd あり |
| 図表 IV-1 | explain_docs/phase2_flow_diagram.mmd | Phase2 候補宇宙形成フロー | mmd あり |
| 図表 V-1 | 新規（Phase7） | Moat の時間軸拡張（完成・変化・新生） | 要作図 |
| 図表 V-3 | explain_docs/phase3_moat_matrix.md | Emerging 産業基盤マップ | md あり→表化 |
| 図表 V-5 | phase3 role_assignment.csv | Final20 役割マトリクス | データあり→表化 |
| 図表 VI-1 | **figures/portfolio_role_weights.png** | 役割別比率 | ✔ 生成済み |
| 図表 VI-2 | **figures/portfolio_sector_weights.png** | 業種別比率 | ✔ 生成済み |
| （VI-3） | **figures/portfolio_theme_weights.png** | テーマ別比率 | ✔ 生成済み |
| 図表 VII-1 | **figures/ablation_overlap.png** | Ablation 結果（A1〜A16 overlap） | ✔ 生成済み |
| （VII-a） | **figures/drawdown_chart.png** | in-sample ドローダウン | ✔ 生成済み |
| （VII-b） | **figures/role_contribution.png** | 役割別寄与 | ✔ 生成済み |

## 2. 表（tables/ + データCSV）

| 論文番号 | ソース | 内容 |
|---|---|---|
| 図表 II-1 | 新規 | 先行研究 ↔ 使用指標の対応 |
| 図表 II-2 | 新規 | 守・破・離の役割 |
| 図表 V-2 | formula_lineage | Transformation Moat 式体系（設計→partial→部品） |
| 図表 V-4 | phase3 evidence_levels.csv | Evidence Level 設計（5系統） |
| Final20 一覧 | phase3 final20_selected.csv | 20社・役割・スコア・証拠 |
| 配分表 | **tables/allocation_table_for_report.csv** | 銘柄別 目標/実配分・株数 |
| リスク要約 | **tables/risk_summary_table.csv** | ボラ・MDD・β・TE・HHI |
| 図表 VII-2 | risk_analysis.md | リスク・限界一覧（10項目） |

## 3. 式（(1)〜(15) ＋ 検証式）

| 番号 | 式 | 章 | 所在 |
|---|---|---|---|
| (1) | B/M | Ⅲ | phase1_formula_explanation |
| (2) | E/P | Ⅲ | 同 |
| (3) | Gross Profitability | Ⅲ | 同 |
| (4) | Piotroski available ratio | Ⅲ | 同 |
| (5) | Sloan Accruals | Ⅲ | 同 |
| (6) | ADV（60日平均売買代金＝流動性） | Ⅲ/Ⅳ | 同 |
| (7)-(9) | Phase2 正規化パーセンタイル・効用・コンセンサス | Ⅳ | phase2_optimization_explanation |
| (10) | Transformation Moat Score（設計形） | Ⅴ | phase3_formula_explanation / lineage |
| (11) | Transformation Moat Score（partial 実装形） | Ⅴ | 同 |
| (12) | Emerging Moat Score | Ⅴ | 同 |
| (13) | Evidence Level | Ⅴ | 同 |
| (14) | Portfolio target weight（risk-adjusted role） | Ⅵ | phase4_allocation_explanation |
| (15) | Unit-share adjusted quantity | Ⅵ | 同 |
| (16) | Sharpe Ratio | Ⅶ | Phase7 で追加（Sharpe1966/1994） |
| (17) | Max Drawdown | Ⅶ | Phase7 で追加 |
| (18) | Jensen's α | Ⅶ | Phase7 で追加（Jensen1968） |
| (19) | HHI | Ⅶ | Phase7 で追加 |

## 4. LaTeX 整形ルール順守チェック
- 文中式 `$...$`／独立式 `\[...\]`／参照式 `equation`。`eqnarray` 不使用。
- `\max \min \log \exp \arg`、上付き語は `S^{\mathrm{Trans}}`。数式中テキストは `\mathrm{}`/`\text{}`。
- 式の直後に変数定義、式の前後に説明文（孤立させない）。→ Phase7 で全式に適用。
