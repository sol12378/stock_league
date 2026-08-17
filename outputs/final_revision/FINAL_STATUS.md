# FINAL STATUS（最終状態・単一の正）

本ファイルが最終状態の唯一の正典である。過去の途中状態・矛盾記述は `history/` に退避した。旧・別様式（STOCK リーグ風カラー版）や旧スコアの記述を最終判断に用いないこと。

## 完成区分
**構造完成版（条件付き提出準備版）。** 分析・論理・図表・式・参考文献・組版・監査は完成。ただし人間記入必須欄（企業紹介の定性記述・インタビュー・振り返り・表紙メタ）が残るため、「完成版」とは呼ばない（`human_completion_guide.md` 参照）。

## 正典データ
| 対象 | 正典 |
|---|---|
| Final20 | `outputs/beyond_buffett_fable_loop_final/phase3_moat_construction/final20_selected.csv` |
| 配分 | `outputs/beyond_buffett_fable_loop_final/phase4_portfolio_allocation/allocation_final.csv` |
| 検証 | `outputs/beyond_buffett_fable_loop_final/phase5_verification_and_ablation/phase5_validation_summary.json` |
| 内容原本 | `final_report_source.md` |
| 数式 | `equation_latex_source.md` / `eqns.py` |
| 書式原本 | 公式学生懸賞論文 Word テンプレート（未入手・要入手）＋ 暫定書式 |

## 成果物（最終）
- `beyond_buffett_final_student_contest.docx`（学生懸賞論文様式・OMML 数式・v11 灰色式ボックス・記入テンプレ）
- `beyond_buffett_final_student_contest.pdf`（LibreOffice 生成・18 ページ・全ページ目視 QA 済み）
- `final_report_source.md` / `equation_latex_source.md` / `formula_inventory.csv` / `formula_lineage_final.md`
- 監査：`independent_review.md` / `data_consistency_audit.csv` / `formula_consistency_audit.md` / `reference_integrity_audit.md` / `style_compliance_audit.md`
- `page_budget.md` / `human_completion_guide.md` / `change_log.md`
- `final_figures/`（モノクロ）/ `final_tables/`

## 検証済みの事実（独立監査・全 PASS）
- Final20 と配分の銘柄は完全一致（20/20）。Phase1 Top5 固定継承。役割 5/5/5/3/2。配分合計 1.0、最大 7.46%。
- Evidence Level L3:15 / L2:4 / L1:1（L1＝4350、Buffett Core、選定は Value×Quality）。
- Transformation：設計式(3.1)は選定未使用、partial 実装式(3.2)で選定（partial 19・lite 1）。TR は識別力ゼロで採用根拠に不使用。
- アブレーション A8（Top100 限定）が最小重複 7、A16 は 16。ベースは Final20 を 20/20 再現。
- **検証は全期間 in-sample・性能主張なし。直近 1 年 Information Ratio = −0.405（負）を本文に明記。** テーマ HHI 0.402。1306.T の分割補正済み。

## ステータス統一（旧矛盾の解消）
- 数式：**OMML（Word ネイティブ、編集可能）**。画像は不使用。
- PDF：**生成済み**（LibreOffice headless。Word でも生成可）。
- 余白：**32/40.5mm**（旧 20/22mm を是正）。見出し：**Word Heading 1〜4 スタイル**（直接書式ではない）。
- 旧 Phase7 スコア（96/97/98）や STOCK リーグ様式の記述は本リビジョンでは無効。旧版は `history/` 参照。

## 残る人間確認事項（提出前必須）
1. 企業紹介の定性欄・一次資料出典の記入（4350 継続性・6430 配当を含む）
2. インタビュー・アンケート（未実施なら「今後の課題」へ）
3. 振り返りの実体験記入
4. 公式 Word テンプレート入手・流し込み・44字×36行実測
5. 単元未満株（S株）可否の確認（不可なら L=100 代替配分）
6. 提出締切・様式の最終確認
