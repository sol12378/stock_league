# Phase1 / Phase2 現状復元記録（Phase0 監査サマリー）

出典: `outputs/phase1_top5/`, `outputs/phase1_final/`, `outputs/phase1_buffett_complete/`, `outputs/phase2_perfect_final_break/`

## 1. Phase1 Top5（Buffett Core・固定）

| rank | code | 社名 | 市場 | sector | B/M | E/P | GP | Piotroski avail | Sloan | 流動性 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3539 | JM HOLDINGS | Prime | Retail Trade | 1.426 (76.0%) | 0.204 (94.8%) | 0.735 (91.8%) | 6/6 | -0.002 | pass |
| 2 | 4350 | MEDICAL SYSTEM NETWORK | Standard | Retail Trade | 1.440 (76.5%) | 0.174 (92.2%) | 0.719 (91.2%) | 6/6 | -0.026 | pass |
| 3 | 6430 | DAIKOKU DENKI | Prime | Machinery | 1.468 (77.4%) | 0.250 (96.8%) | 0.466 (78.5%) | 4/6 | +0.001 | pass |
| 4 | 7803 | Bushiroad | Growth | Other Products | 1.442 (76.6%) | 0.205 (94.9%) | 0.401 (72.2%) | 6/6 | -0.044 | pass |
| 5 | 9470 | GAKKEN HOLDINGS | Prime | Info & Comm | 1.526 (79.6%) | 0.122 (82.1%) | 0.395 (71.3%) | 6/6 | -0.023 | pass |

- 全社 distress 除外なし・異常値なし・流動性 pass。目標配分 20〜25%（final20_structure_plan）。
- 選定は**重み付き合成スコアなし**の段階的スクリーニング＋逐次 tie-break（GP→E/P→B/M→Piotroski→Sloan→流動性→時価総額）、同一業種原則2社まで。
- ファネル実数: 3,099 → 2,740（Value）→ 583（Quality）→ 146（Fin. Strength）→ 112（Earnings Quality）→ 90（Distress）→ 77（Liquidity）→ Top5。
- Top5 は sector-adjusted final20 の rank 1,2,5,6,7 に対応（rank3=9990、rank4=8278 は同一業種上限で Top5 から除外——意図的で整合）。

## 2. Phase1 手法（先行研究式のみ）

| 指標 | 定義 | 出典 | 実装状況 |
|---|---|---|---|
| B/M | BE/ME | Fama-French (1993) | 完全実装 |
| E/P | Earnings/ME（正の利益のみ） | Basu (1977, 1983) | 完全実装 |
| GP | Gross Profit / Total Assets | Novy-Marx (2013) | 実装（カバレッジ98.2%） |
| Piotroski | 9シグナル中 **6実装**（available ratio ≥ 0.65） | Piotroski (2000) | 部分実装・明示開示 |
| Sloan Accruals | (NI − CFO)/平均TA、悪い側上位30%除外 | Sloan (1996) | 完全実装 |
| Ohlson O / Altman Z | 倒産予測 | Ohlson (1980)/Altman (1968) | **原式未実装**（入力欠損）→ simple distress guardrail で代替・開示済み |
| Liquidity | 60日平均売買代金（300万未満除外/1000万以上pass） | 実務ガードレール | 実装 |

既知の限界（開示済み）: Piotroski 6/9、Ohlson/Altman 未実装、GP の小売バイアス、current data での look-ahead bias、配当データ乖離（6430: chosen DPS 4.25% vs trailing 0%）。

## 3. Phase2 手法（式は変えず使い方を最適化）

- **Phase1 式の定義は不変**（明示）。最適化対象＝正規化方式・重み・TopN・業種調整・欠損処理（selected_method = random_search_real）。
- 採用解: normalization=market_percentile、重み liquidity .330 / distress .251 / bm .184 / gp .147 / ep .057 / sloan .021 / piotroski .010、ペナルティ anomaly .297 / missing .259 / microcap .199 / onetime .195、sector_adjustment=false、missing_handling=exclude_if_core_missing。
- **formal_top1200 が正式母集団**（Top100=優先確認、Top300=主要分析、Top2000=参照群のみ）。Phase1 Top5 のカバレッジ 5/5。
- 選定前除外: distress_hard_exclude 184、negative_equity 11、金融業 0（元から0行）。
- 検証: strict walk-forward 未完了（fold不足・開示済み）→ point-in-time fixed-weight out-of-time validation（2023/2024/2025 snapshot）で代替。**将来リターン予測力は主張しない**。
- pass/fail: **全15項目 PASS**。validation errors なし。
- Phase2→Phase3 ハンドオフ: review flags は除外理由ではなく確認論点。phase3_review_required=825（flag_audit）/840（final_audit）— 15件の不一致あり。sector HHI 0.0707、最大業種シェア 11.6%。

## 4. Phase0 監査で検出した文書間不整合（本ループでの扱い）

| # | 不整合 | 本ループでの処理 |
|---|---|---|
| 1 | phase3_review_required 件数: 840 vs 825 | Phase2 レビューで注記。最終レポートでは「約8百強（825〜840、集計時点差）」とせず、flag_audit_report の 825 を採用し脚注で差異を開示 |
| 2 | Top5 と sector-adjusted final20 の rank 非連続 | Phase1 説明資料で「同一業種2社まで」制約を一元的に説明 |
| 3 | distress 重み 0.251 vs ablation 寄与 0.0017 | hard exclusion 併用による限界効果の消失として Phase2 説明資料に明記（手法の誠実な開示として扱う） |
| 4 | 金融業除外 applied=true / excluded=0 | 「母集団構築段階で金融業は既に除外済みのため追加除外0」と表現統一 |
| 5 | fixed-weight validation レポートの表が空 | 実データは walk_forward/ 配下 CSV に存在。Phase2 レビューで参照先を明記 |
