# Phase6 Repair Tasks（loop 1）

統合レビュー 97/100 で PASS。critical issue なし。以下は Phase7 で吸収 or 人間確認。

| ID | 内容 | 対応 | 状態 |
|---|---|---|---|
| R6-0 | 感度分析 ρ の過大記載（0.997→Trans0.997/Emerg0.994） | phase3_explanation_for_report 修正 | **本ループで解消** |
| R6-1 | 図の日本語ラベル docx 体裁確認 | Phase7 docx 生成時 | Phase7 |
| R6-2 | 公式 Word テンプレート（Moodle）未入手 | 提出前に流し込み | 人間確認 |
| R6-3 | 44字 vs 46字の要項矛盾 | テンプレート実測で確定（本ループは44字で設計） | 人間確認 |
| R6-4 | Phase3「離」の学術文献追補（東証2023・伊藤レポート・Lev&Gu 等） | final_references.md で本文引用と同時追加 | Phase7 |
| R6-5 | 検証式 Sharpe/MDD/Jensenα/HHI を式(16)-(19)として整形 | final_report_latex_equations.md | Phase7 |
| R6-6 | 図表 I-1/II-1/II-2/V-1/V-2/V-4/V-5 を本文用に作図・表化 | Phase7 final_figures/final_tables | Phase7 |

これらは PASS を妨げない。R6-2/R6-3 は環境上解決不能（人間確認事項）。
