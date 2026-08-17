# BEYOND BUFFETT — Fable Loop 最終成果物

日経 STOCK リーグ向け研究プロジェクト「バフェットを超えろ」の最終提出可能成果物。バフェット型投資の本質である **Moat（持続的競争優位）を出発点とし、それを完成・変化・新生の三世代へ時間軸拡張**する枠組みを、守・破・離（Phase1・Phase2・Phase3）として構築し、最終20社ポートフォリオ・理論的配分・検証・最終論文まで、ループエンジニアリングで完成させた。

## 結論サマリ

- **全 Phase（1〜7）が 95 点以上で PASS。loop 1 で成功終了。**
- **Final20**（役割・不変）:
  - Buffett Core 5（Phase1 Top5 固定）: 3539, 4350, 6430, 7803, 9470
  - Transformation Core 5: 5902, 9828, 5233, 8037, 3863
  - Emerging Core 5: 6368, 6315, 6920, 6526, 5803
  - Dual Moat 3: 3697, 6841, 9474 ／ Bridge 2: 3089, 2112
- **配分**: 案C（リスク調整役割配分、式(14)）。役割 25/25/25/15/10。最大銘柄 9474=7.46%。L=1 で ¥4,949,198 投資・消化率 99.0%。
- **検証**（in-sample・性能主張なし）: 3年 Sharpe 1.41・Jensen α +7.3%・β 0.925・MDD −24.9%。**1年 IR −0.405（負）を誠実に開示**。Ablation A1〜A16 で単一要素依存を否定、A8（Top100 限定）が最小＝母集団拡張が最大の駆動要因。

## ディレクトリ構成

| ディレクトリ | 内容 |
|---|---|
| `phase0_input_audit/` | 入力棚卸し・欠損監査・正典階層・書式抽出・v2 欠陥 D1〜D9 |
| `phase1_review/` | 「守」レビュー（scorecard/score.json/…/explanation_for_report） |
| `phase2_review/` | 「破」レビュー |
| `phase3_moat_construction/` | 「離」Moat構築（Final20・スコア・証拠・役割・式系譜） |
| `phase4_portfolio_allocation/` | 配分4案・最終案C・単元株調整・分析 |
| `phase5_verification_and_ablation/` | 市場比較・リスク指標・Ablation(A1-A16)・リスク分析 |
| `phase6_integrated_review/` | 統合レビュー7点（整合監査・アウトライン・図表式在庫・参考文献監査） |
| `phase7_final_report/` | 最終論文（**日経 STOCK リーグ入賞レポート様式**）md/**docx**（カラーバナー・式画像・記入テンプレート）/**PDF（19頁・Word 生成済み）**/式集/図/表/参考文献/チェックリスト。`final_report_academic_variant.md` は旧アカデミック構成の控え |
| `explain_docs/` | 各 Phase の説明資料・フロー図(.mmd)・式解説 |
| `figures/` `tables/` | 生成図・表 |
| `scripts/` | phase3_rebuild / phase4_allocation / phase5_validation / phase5_ablation / phase7_concept_figures / phase7_build_docx |
| `logs/` | loop_state.json 等 |

## 最初に見るべきファイル

1. `FINAL_LOOP_READINESS_CHECK.md` — 全チェック PASS/FAIL
2. `phase7_final_report/final_report.md` — 最終論文（STOCK リーグ様式・内容原本）／ `final_report.docx`（カラーバナー・式画像・記入テンプレート入り）／ `submission_checklist.md`（提出者の記入箇所）
3. `phase6_integrated_review/integrated_review_scorecard.md` — 統合スコア 97
4. `phase5_verification_and_ablation/ablation_report.md` — A1〜A16
5. `phase4_portfolio_allocation/allocation_analysis.md` — 配分決定
6. `phase3_moat_construction/phase3_formula_lineage.md` — 式の系譜

## 正典（source hierarchy）

- Phase1 Top5: `outputs/phase1_top5/phase1_buffett_core_top5.csv`
- Phase2 母集団: `outputs/phase2_perfect_final_break/formal_top1200/`
- Phase3: `outputs/phase3_beyond_buffett_v2/`（v1 は差分監査用）
- 価格: `data/processed/prices_daily.parquet`（TOPIX=1306.T, 日経=^N225）
- 書式: `docs/2026年度募集要項.docx`

## 再現方法

```
.venv/bin/python outputs/beyond_buffett_fable_loop_final/scripts/phase5_ablation.py       # A1-A16
.venv/bin/python outputs/beyond_buffett_fable_loop_final/scripts/phase7_concept_figures.py # 概念図
.venv/bin/python outputs/beyond_buffett_fable_loop_final/scripts/phase7_build_docx.py      # docx
```

## 注意

- 検証は全区間 **in-sample**（ポートは 2026-06 データで構築）。**リスク特性の確認であり将来リターンの予測ではない**。
- 1306.T の未調整 1:10 分割（2026-03-30）は ×10 補正済み（`scripts/phase5_validation.py`）。
- 人間確認事項（テンプレート・締切・PDF書き出し・単元株裏取り等）は `FINAL_LOOP_READINESS_CHECK.md` 末尾を参照。
