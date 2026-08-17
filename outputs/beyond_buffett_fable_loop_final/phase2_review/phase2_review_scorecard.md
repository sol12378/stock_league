# Phase2「破」Review Scorecard（loop 1）

採点日: 2026-07-10／採点対象: `outputs/phase2_perfect_final_break/`（正典）＋ `docs/explain_docs/phase2_methodology_report_polished.tex`

## 総合: **96 / 100 → PASS（≥95）**

| 基準 | 配点 | 得点 | 根拠 |
|---|---|---|---|
| 1. Phase1 式の非改変性 | 20 | 20 | 「Phase1 で採用した先行研究式の定義は変更せず、式の**使い方**を最適化した」ことを明示。守った項目リスト（式定義・Value×Quality×Safety 思想・金融業除外・distress hard exclude・Future Moat 不使用・リターン最大化を主目的にしない）が文書化。tex にも「変えない式」の独立章 |
| 2. 候補宇宙形成の妥当性 | 20 | 19 | formal_top1200 は「広さ・品質・安全性・流動性・業種分散・解釈可能性・Phase3 review 負荷」の総合判断として採用され、utility 最適（Top2000）をあえて採らなかった理由も開示。Phase1 Top5 カバレッジ 5/5。sector HHI 0.0707・最大業種 11.6% と分散良好。−1: utility 関数が breadth を報酬する設計であるため Top1200 の選択自体は定量最適ではなく判断（ただし判断過程は開示済み） |
| 3. 閾値最適化の説明力 | 20 | 19 | selected_method=random_search_real、採用解の重み・ペナルティ・正規化（market_percentile）・欠損処理が JSON で完全開示。4 正規化方式のコンセンサスタグで頑健性を担保。−1: **distress の重み 0.251 に対し ablation 寄与 0.0017** という乖離の説明が原文書に不足（hard exclusion 併用で限界効果が消失する構造。本ループの説明資料で補完） |
| 4. Phase3 への接続性 | 20 | 19 | ハンドオフ文書が「review flags は除外理由ではなく確認論点」を明確化。Top100/300/1200/2000 の役割区別が明文化。**Phase2 スコア（Exploratory Weighted Buffett Score）は正式な Phase1 式ではなく最終スコアでもない**ことを README に明記。−1: phase3_review_required 件数が 840（final_audit）と 825（flag_audit）で不一致 |
| 5. 監査・欠損・限界記述 | 20 | 19 | 欠損入力なし・validation errors なし・GP 定義監査（unverified 29 件=2.67% を明示）・flag 監査・distress 除外 184+11 件の完全開示。strict walk-forward 未完了を隠さず fixed-weight out-of-time validation で代替し、**「将来リターン予測力を主張しない」** と禁止表現まで規定。−1: fixed_weight_out_of_time_validation_report.md の表がヘッダのみで、実データが walk_forward/ 配下 CSV にしかない（参照導線の欠落） |

## 判定

- **Phase2 は「破」として成立**：式は不変、最適化対象は閾値・分位・通過条件・正規化・TopN に限定。候補宇宙形成が目的であり銘柄選定ではない。
- 残余 4 点は説明の補完で吸収可能（本ループの explain_docs/phase2_* で対応済み）。
