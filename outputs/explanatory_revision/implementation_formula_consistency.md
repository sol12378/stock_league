# 式 ⇔ 実装コード 一致監査

本文の各式が、正典コード（`phase3_common.py` / `phase3_v2_pipeline.py` / `phase4_allocation.py`）と一致することを確認した。前回版から**実データに合わせて訂正した点**を最上部に明示する。

## 実データに合わせた訂正（重要）

| 箇所 | 前回の記述 | 正典コードの実装 | 本版の対応 |
|---|---|---|---|
| 式(1.7) 危機ガードレール：連続赤字 | 「2期連続」 | **純利益3期連続マイナス**（`persistent_loss_flag`＝recent3 が全て<0、L208） | cases 式を**3期連続**に訂正 |
| 式(1.7) 危機ガードレール：営業CF | 「当期CFO<0 をハード除外条件に含む」 | **negative_cfo は base_hard_exclusion に含まれない**（債務超過・連続赤字・distress・流動性・異常値・欠損のみ、pipeline L381-397）。当期CFO赤字は value_trap_penalty（ソフト） | 式(1.7)から当期CFOを除外し、式(3.2)のバリュートラップ罰の要素として説明 |

前回ユーザーへ「実装一致＝3期連続・当期CFO」と回答したが、正典コードを精査した結果、**当期CFOはハード危機判定に含まれない**ことが判明したため、本版で式・本文を実装どおりに訂正した（「実データを元に」の指示に従う）。

## 一致確認一覧

| 式 | 実装箇所 | 一致 |
|---|---|:--:|
| 1.0 時価総額 | 株価×株式数（market_equity_final） | ✔ |
| 1.1 B/M / 1.2 E/P | bm_raw / ep_raw | ✔ |
| 1.3 GP | gross_profitability | ✔ |
| 1.4 Piotroski | piotroski_available_ratio（9→6シグナル部分実装） | ✔ |
| 1.5 Sloan | sloan_accruals | ✔ |
| 1.6 流動性 | avg_trading_value_60d、閾値≈1,000万円 | ✔ |
| 1.7 危機ガードレール | negative_equity_flag ∨ persistent_loss_flag（3期連続）＝base_hard_exclusion の財務中核 | ✔（訂正後） |
| 2.1 正規化 / 2.2 コンセンサス | 市場percentile・4方式コンセンサス（core970/robust1135） | ✔ |
| 2.3 Phase2信頼度 | phase2_confidence_score＝clip(1+.05core+.03robust−.10outlier−.15fragile−…,0,1.1) | ✔ |
| 3.1 Trans設計形 | 選定未使用（付録）。R・E データ欠如 | ✔（未使用と明記） |
| 3.2 Trans実装形 | transformation_score（partial 19/lite 1）。R→FCF代替・E除外 | ✔ |
| 3.3 Emerging | emerging_score（証拠加点≤8・keyword_only 18点罰・577社除外） | ✔ |
| 3.4 Evidence Level | final_evidence_level（役割別 min/max、L3:15/L2:4/L1:1、L1＝4350） | ✔ |
| 4.1 配分 | w_risk＝役割予算×(ℓ×e×c÷σ)/Σ、8%上限、ℓ∈{1.00,0.85,0.70}、e=1+0.05(L−2)、c=0.5+0.5conf、σ下限0.10 | ✔ |
| 4.2 単元株・再配分 | floor((Bω)/(PL))×L。8%超→同役割内比例再配分・最大5回・役割間移動なし・端数は残現金 | ✔ |
| 5.1–5.5 検証式 | phase5_validation_summary.json（Sharpe1.41/α+7.3%/β0.925/1年IR−0.405/HHIテーマ0.402） | ✔（選定未使用） |

## 補足
- 式(1.7)の「distress」には Phase1 の `distress_exclusion_flag`（112→90 の除外）も含まれるが、本文の式は財務的に明確な2条件（債務超過・3期連続赤字）に絞って提示し、他のハード除外（流動性＝式1.6、異常値、欠損過多）は別途本文で言及する。
- Final20 は全社 D=0（危機フラグなし）。D=1 の数値例は説明用の架空企業（本文で「説明用」と明記）。
