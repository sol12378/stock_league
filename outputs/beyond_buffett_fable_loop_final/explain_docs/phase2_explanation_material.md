# Phase2「破」説明資料（explanation material）

## まず結果

- 正式母集団 **formal_top1200** を形成（Top100=優先確認、Top300=主要分析、Top2000=参照群のみ）。
- Phase1 Top5 のカバレッジ 5/5。distress ハード除外 184 社＋債務超過 11 社。金融業は母集団構築段階で除外済み（追加除外 0）。
- 業種分散: HHI 0.0707、最大業種シェア 11.6%。
- 判定: 全 15 監査項目 PASS、validation errors ゼロ。

## 何を守り、何を破ったか

| 守った（不変） | 破った（最適化対象） |
|---|---|
| B/M・E/P・GP・Piotroski・Sloan・Distress・Liquidity の式定義 | 固定閾値（上位30%等）→ 重み・分位の探索 |
| Value×Quality×Safety の思想 | 固定候補数 → TopN 比較（100/300/1200/2000） |
| 金融業除外・distress ハード除外 | 単一正規化 → 4方式コンセンサス |
| Future Moat / AI テーマを入れない | 単一時点評価 → point-in-time panel |
| 将来リターン最大化を目的にしない | 欠損処理・業種調整の比較 |

## 採用解（selected_phase2_solution_clean.json）

- 手法: random_search_real／正規化: market_percentile／欠損: exclude_if_core_missing／業種調整: 不採用
- 指標重み: liquidity 0.330 / distress 0.251 / bm 0.184 / gp 0.147 / ep 0.057 / sloan 0.021 / piotroski 0.010
- ペナルティ: anomaly 0.297 / missing 0.259 / microcap 0.199 / onetime 0.195

> **distress 重みのパラドクス（重要）**：distress の重みは2番目に大きいが、除去実験での目的関数低下は 0.0017 とほぼゼロ。これは distress ハード除外（184+11社）が先に効いており、通過母集団内では distress スコアの分散が小さいため。**多層防御（除外＋微調整）であり、重み=予測力ではない**。

## 検証の位置づけ

- strict true walk-forward: **未完了**（fold 不足を開示）。
- 代替: point-in-time fixed-weight out-of-time validation（EDINET 提出日ベース panel、2023/2024/2025 snapshot に固定重みを適用）。実データは `outputs/phase2_perfect_final_break/walk_forward/fixed_weight_annual_validation.csv`（レポート md の表は空のため CSV を一次ソースとする）。
- 許される主張:「時点外でも候補群の品質が保たれることを確認した」。禁止される主張:「将来リターンの予測力を証明した」。

## Phase3 への引き渡し

- review flags は**除外理由ではなく確認論点**（phase3_review_required 825 社。final_audit 側集計は 840 で 15 件の時点差あり、825 を採用）。
- 内訳: outlier_sensitive 622 / top300_priority_check 200 / top100_priority_check 100 / normalization_fragile 29 / GP unverified 29 / GP proxy 3 / sector_adjusted_only 19。
- Phase2 スコアは Phase3 では confidence 情報（0.10 の重みで実行信頼性の一部）としてのみ利用し、**最終選定スコアには使わない**。

## 限界

- GP 定義未検証 29 社（2.67%）。年度別 panel では unverified 率が上がる（2023: 7.3% → 2025: 8.7%）。
- Top1200 は utility 最適（Top2000）ではなく判断による採用（判断過程は開示済み）。
- 探索的重み付きスコアはあくまで候補宇宙形成の道具。
