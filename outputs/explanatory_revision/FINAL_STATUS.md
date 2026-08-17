# FINAL STATUS（説明論文リビジョン・最終状態の唯一の正）

## 完成区分
**条件付き完成（構造完成版）。** 自動生成部分（本文・全22式の8項目解説・図表・通し計算・用語集・監査）は完成。人間記入欄（企業紹介の定性記述・インタビュー・振り返り）が残るため「完成」とは呼ばない。

## 成果物 `outputs/explanatory_revision/`
| ファイル | 内容 |
|---|---|
| `beyond_buffett_explanatory_report.docx / .pdf` | 詳細解説版（28頁・全8項目・付録に設計式3.1＋Ohlson/Altman） |
| `contest_report_30pages.docx / .pdf` | 30頁提出版（23頁＋人間記入枠、圧縮8項目、記入テンプレ入り） |
| `data_real.json` | Final20 全社の実測指標（正典CSV由来） |
| `symbol_dictionary.csv` | 全79記号（記号/和名/データ/計算/範囲/意味） |
| `term_dictionary.md` | 用語集20語 |
| `formula_latex_source.md` | 全22式の LaTeX（cases 含む） |
| `formula_explanation_audit.csv` | 8項目×22式の充足監査（全 YES） |
| `implementation_formula_consistency.md` | 式⇔実装コード一致監査（Distress訂正を明記） |
| `phase_input_process_output.md` | Phase別 入力/処理/出力＋ファネル |
| `full_numerical_example.md` | 9470 の通し計算12ステップ（実データ） |
| `beginner_readability_review.md` | 初学者QA・完成判定 |
| `page_budget.md` / `change_log.md` / `REVISION_PLAN.md` | 頁予算・変更履歴・計画 |
| `final_figures/` | モノクロ図5点 / `rendered_pages/` 内部QA（提出物に含めない） |
| `scripts/` | eqns_explained.py・report_lib.py・build_explanatory.py・docxlib.py |

## 検証済みの事実（実データ準拠）
- 全式の数値例・変数表・通し計算は正典データ（scoring_master / allocation_final / phase5_validation_summary）に一致。
- **Distress式(1.7)は実装一致（債務超過 ∨ 3期連続赤字）**。当期CFO赤字はハード除外に含まれず、バリュートラップ罰の要素として扱う（前回回答からの訂正）。
- 設計式(3.1)は選定未使用（付録）／実装形(3.2)で選定（partial19・lite1）。
- 検証は in-sample・成績主張なし・**1年 IR −0.405（負）を本文明記**。
- Final20・配分・役割 5/5/5/3/2 は前リビジョン（`../final_revision/`）と同一の正典データ。

## 品質QA（LibreOffice レンダリング・全ページ目視）
- v11式ボックス（灰帯＋OMML＋変数）非分割、cases 式（1.7・3.4）正常表示、変数表・配分表はページ内、豆腐・文字化けなし、A4・余白32/40.5mm。
- 詳細版28頁／提出版23頁（人間記入後も≤30見込み）。DOCX と PDF の内容一致。

## 残る人間確認事項（提出前必須）
1. 企業紹介20社の定性欄・一次資料出典（4350 継続性・6430 配当を含む）
2. インタビュー・アンケート（未実施なら「今後の課題」へ）
3. 振り返りの実体験記入
4. 公式 Word テンプレート入手・流し込み・44字×36行実測
5. 単元未満株（S株）可否確認（不可なら L=100 代替配分）

## 位置づけ
本リビジョンは `../final_revision/`（学生懸賞論文様式・v11式ボックス）を、初学者可読性の観点で全面改修したもの。分析データは共通・不変。矛盾時は本 FINAL_STATUS を優先。
