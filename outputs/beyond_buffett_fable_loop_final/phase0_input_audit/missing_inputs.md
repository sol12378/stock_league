# Missing Inputs Report（欠損入力の監査）

生成日: 2026-07-10（loop 1）

## 1. 想定入力に対する充足状況

| 想定入力 | 状況 | 対応 |
|---|---|---|
| `phase2_perfect_final_break(1).zip` | **同名ファイルは不存在** | 同一内容の `outputs/phase2_perfect_final_break.zip`（展開済みフォルダあり）を正として採用 |
| `phase3_beyond_buffett.zip` | あり（展開済み） | v1 として差分監査に使用 |
| `phase3_beyond_buffett_v2.zip` | あり（展開済み） | **正典として採用** |
| `docs/explain_docs/phase1*` | あり（tex + pdf 2世代） | flow_v2 を式スタイル正典に |
| `docs/explain_docs/phase2*` | あり（tex + pdf 2世代） | polished を式スタイル正典に |
| **`docs/outliers*`** | **不存在（プロジェクト全体を深さ無制限で探索、ファイル名一致 0件）** | 式セクション様式の抽出元として指定されていたが存在しない。代替として `explain_docs` の tex 2本から同等の様式を抽出（→ `outliers_style_extraction.md` 参照） |
| `2026年度募集要項.docx` | あり | 書式制約を全文抽出済み（→ `report_format_requirements.md`） |
| 学生懸賞論文テンプレート（Word） | **不存在**（Moodle 配布物、リポジトリ未収録） | 要項記載のページ設定（44字×36行、余白左右32mm・上下40.5mm）を手動再現する。**人間確認事項**：提出前に必ず公式テンプレートに流し込むこと |
| 価格データ | あり：`data/processed/prices_daily.parquet`（4,349,347行、3,650銘柄、2021-06-01〜、^N225・1306.T 含む） | Phase5 実データ検証に使用 |
| 財務データ | あり：`data/processed/fundamentals_clean.csv` ほか、Phase2 point-in-time panel | Phase3/5 で使用 |
| 開示テキスト | 部分的：`data/processed/edinet_documents.csv`、Phase3 v2 の `phase3_disclosure_enrichment.csv` | Evidence Level は v2 の付与済み値を監査の上で採用 |
| 単元株数データ | **専用ファイル不存在** | 東証の単元株制度により全上場銘柄 100株に統一済み（2018年10月完了）であることを根拠に **L_i = 100 を仮定**。仮定であることを Phase4 に明記（人間確認事項） |
| ポートフォリオ配分データ | あり：`phase3_beyond_buffett_v2/data/phase3_allocation_plan.csv` | Phase4 の比較基準として使用 |

## 2. 要項・提出関連の欠落

- 具体的な**提出締切日**は要項本文に明示なし（Moodle 掲載のチェックリスト・応募用紙側に依存）。→ 人間確認事項。
- 要項内で **1行字数が 44字と46字で矛盾**（本文執筆要領は44字×36行、部門規定は46字×36行）。→ 安全側の 44字×36行 で設計し、テンプレート実測での最終確認を人間確認事項とする。

## 3. Phase1/Phase2 由来の既知欠損（上流から継承）

- Ohlson O-Score / Altman Z-Score の原式入力変数（GNP price-level index, working capital, retained earnings, strict EBIT 等）欠損 → simple distress guardrail による代替（Phase1 で開示済み）。
- Piotroski F-Score は 9 シグナル中 6 実装（available ratio 方式で開示済み）。
- Gross Profitability の定義未検証 29 件（formal_top1200 の 2.67%）。
- 配当データ：6430 の chosen DPS と trailing DPS の乖離（4.25% vs 0%）→ レポートで断り書き。
- strict true walk-forward は fold 不足で未完了（fixed-weight out-of-time validation で代替、開示済み）。

## 4. 結論

**即停止を要する欠損はない。** ただし上表の「人間確認事項」（公式Wordテンプレート、提出締切、単元株=100株仮定、字数矛盾）は FINAL_LOOP_READINESS_CHECK.md に引き継ぐ。
