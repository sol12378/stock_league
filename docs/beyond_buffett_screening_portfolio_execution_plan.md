# BEYOND BUFFETT レポート実行・実装計画書
## Ⅱスクリーニング / Ⅲポートフォリオ決定 / ポートフォリオ配分・銘柄紹介 / パフォーマンス分析

作成日: 2026-06-01  
対象: 日経STOCKリーグ提出レポート草案  
テーマ: **BEYOND BUFFETT ——「完成された堀」から「進化する堀」へ——**

---

## 0. 本計画書の位置づけ

本計画書は、日経STOCKリーグ提出レポートにおける以下の章を実際に作成するための実行計画・実装計画・求めるアウトカムを整理したものである。

- **Ⅱ スクリーニング**
- **Ⅲ ポートフォリオ決定**
  - **1. ポートフォリオ配分・銘柄紹介**
  - **2. パフォーマンス分析**

添付された優秀レポートでは、単なる銘柄紹介ではなく、独自概念を定義したうえで、それを複数段階のスクリーニングに落とし込み、最終的なポートフォリオ配分とパフォーマンス分析まで一貫して説明している。

たとえば、OUTLIERレポートでは、グロース市場609社を対象に、3段階のスクリーニングで522社、41社、20社へと絞り込む構成を採用している。また、Hybrid Activist-PE Modelでは、非金融上場企業3,611社を対象に、多段階スクリーニングで20社を抽出し、その後に配分式とパフォーマンス分析を行っている。

本レポートでも同様に、以下の流れで構成する。

```text
東証上場企業全体
  ↓
Ⅱ スクリーニング
  ↓
最終20銘柄
  ↓
Ⅲ-1 ポートフォリオ配分・銘柄紹介
  ↓
Ⅲ-2 パフォーマンス分析
  ↓
投資テーマの妥当性検証
```

---

# Ⅱ スクリーニング

## 1. 章の目的

スクリーニング章の目的は、東証上場企業全体から、今回の投資テーマである **BEYOND BUFFETT企業** を客観的に抽出することである。

BEYOND BUFFETT企業とは、以下の3要素を持つ企業である。

1. **既存の競争優位**  
   バフェット型投資の中核であるMoatを持つ企業。

2. **変革余地**  
   日本企業特有の資本効率改善・株主還元・事業構造改革によって再評価されうる企業。

3. **AI時代の新しい堀**  
   AI、データセンター、半導体、電力、通信、業務データ、セキュリティ、現場実装などによって将来の競争優位が深まる企業。

この章で求められるのは、単に「よさそうな企業」を並べることではない。優秀レポートの型に合わせ、**独自概念 → 指標化 → 多段階スクリーニング → 通過企業数 → 最終候補** の流れを明確にする。

---

## 2. 実行計画

## 2.1 対象企業の定義

### 対象市場

本レポートでは、初期母集団を **東証上場企業全体** とする。

対象市場は以下の3つである。

| 市場 | 今回の扱い | 位置づけ |
|---|---|---|
| プライム | 中心候補 | 既存Moat、変革余地、AIインフラ企業を探索 |
| スタンダード | 独自性の源泉 | ニッチトップ、見落とされた変革余地企業を探索 |
| グロース | 限定的に採用 | Future Moat候補。ただしリスクが高いため比率制限 |

### 除外対象

以下は通常の事業会社分析と異なるため、初期段階で除外する。

- ETF
- REIT
- インフラファンド
- 優先株
- 外国株
- 株価データが取得できない銘柄
- 極端に流動性が低い銘柄

### 金融銘柄の扱い

金融銘柄は除外しない。ただし、銀行・保険・証券は一般事業会社と財務構造が異なるため、以下のように扱う。

- ROICや自己資本比率を一般企業と同列比較しない
- 金融銘柄用の補助評価を用いる
- 採用する場合は、収益力、還元姿勢、リスク分散、グローバル展開など、採用理由を本文で明示する

---

## 2.2 スクリーニング段階

本レポートでは、以下の5段階で企業を絞り込む。

| 段階 | 名称 | 目的 | 想定アウトプット |
|---|---|---|---|
| 第1 | 投資適格性 | 分析・投資対象として最低限成立する企業を残す | `universe_filtered.csv` |
| 第2 | Moat Score | 既存の競争優位を測る | `moat_scores.csv` |
| 第3 | Transformation Score | 変革余地を測る | `transformation_scores.csv` |
| 第4 | Future Moat Score | AI時代の新しい堀を測る | `future_moat_scores.csv` |
| 第5 | 定性評価・分散調整 | 最終20銘柄を決定する | `final_candidates.csv` |

---

## 2.3 第1スクリーニング：投資適格性

### 目的

投資対象として最低限の条件を満たす企業を抽出する。

### 実行内容

1. 東証上場銘柄一覧を読み込む
2. 普通株以外を除外
3. yfinanceで株価取得可能か確認
4. 過去3年以上の株価データがあるか確認
5. 直近60営業日の平均売買代金を計算
6. 極端な低流動性銘柄を除外
7. 債務超過・継続赤字など重大な財務リスクを確認

### 使用式

平均売買代金:

```text
平均売買代金_i = mean(Close_i,t × Volume_i,t)
```

### 実装計画

使用モジュール:

```text
src/data/load_jpx.py
src/data/fetch_yfinance.py
src/screening/universe_filter.py
```

入力:

```text
data/raw/jpx/listed_companies.xlsx
data/processed/latest_prices.csv
data/processed/prices_daily.parquet
```

出力:

```text
data/processed/universe.csv
data/processed/universe_filtered.csv
data/processed/screening_summary.csv
```

### 求めるアウトカム

| 成果物 | 内容 |
|---|---|
| `universe.csv` | 東証上場企業全体の母集団 |
| `universe_filtered.csv` | ETF/REIT等除外後の対象企業 |
| `screening_summary.csv` | 初期対象社数、第1通過社数 |
| レポート本文 | 「東証全上場企業から分析対象を定義した」説明 |

---

## 2.4 第2スクリーニング：Moat Score

### 目的

バフェット型投資の中核である既存の競争優位を評価する。

### 理論的根拠

Asness, Frazzini, Pedersen の **Quality Minus Junk** の考え方を参考にする。同研究では、高品質企業を収益性、成長性、安全性、株主還元などから捉えており、本レポートではそのうちMoatに近い要素を、収益性、キャッシュ創出力、安定性、競争地位として再構成する。

### 使用式

標準化:

```text
z(x_i) = (x_i - mean(x)) / std(x)
```

Moat Score:

```text
Moat Score_i
= 0.35 × Profitability_i
+ 0.25 × CashGeneration_i
+ 0.20 × Stability_i
+ 0.20 × CompetitivePosition_i
```

構成要素:

```text
Profitability_i
= average_z(営業利益率, ROE, ROIC)
```

```text
CashGeneration_i
= average_z(営業CFマージン, FCFマージン)
```

```text
Stability_i
= average_z(-営業利益率の標準偏差, -売上成長率の標準偏差)
```

```text
CompetitivePosition_i
= average_z(粗利率, 研究開発費率, 海外売上比率)
```

### 実行内容

1. EDINET APIから財務データを取得
2. 売上高、営業利益、純利益、営業CF、研究開発費などを整備
3. 各指標を算出
4. 外れ値をwinsorize
5. z-score化
6. Moat Scoreを算出
7. 上位企業を抽出

### 実装計画

使用モジュール:

```text
src/data/fetch_edinet.py
src/data/parse_edinet_xbrl.py
src/data/build_fundamentals.py
src/screening/scoring.py
```

出力:

```text
data/processed/moat_scores.csv
data/processed/fundamentals_clean.csv
reports/figures/score_distribution_moat.png
```

### 求めるアウトカム

| 成果物 | 内容 |
|---|---|
| `moat_scores.csv` | 各企業のMoat Scoreと内訳 |
| `score_distribution_moat.png` | Moat Score分布 |
| レポート図表 | Moat Score上位企業表 |
| レポート本文 | 「既存の堀」を定量化した説明 |

---

## 2.5 第3スクリーニング：Transformation Score

### 目的

日本企業特有の変革余地を評価する。単なる割安株ではなく、事業の強さを持ちながら、資本効率改善や株主還元によって再評価される企業を抽出する。

### 理論的根拠

Piotroski F-Scoreの考え方を参考にする。F-Scoreは低PBR企業の中から財務的に強い企業を識別する手法である。本レポートではこれを日本株改革の文脈に拡張し、割安性、資本効率改善、株主還元、改革実行の兆候を測る。

### 使用式

```text
Transformation Score_i
= 0.35 × ValuationGap_i
+ 0.25 × CapitalEfficiencyImprovement_i
+ 0.20 × ShareholderReturn_i
+ 0.20 × ReformEvidence_i
```

構成要素:

```text
ValuationGap_i
= average_z(1/PBR, 1/PER, 1/EV_EBITDA)
```

```text
CapitalEfficiencyImprovement_i
= average_z(ROE改善率, ROIC改善率, 営業利益率改善率)
```

```text
ShareholderReturn_i
= average_z(配当利回り, 総還元性向, 自己株買い比率)
```

```text
ReformEvidence_i
= average_z(中計ROE目標有無, 自己株買い有無, 政策保有株縮減有無)
```

初期実装版:

```text
Transformation Score_i
= 0.35 × z(1/PBR)
+ 0.20 × z(1/PER)
+ 0.20 × z(ROE改善率)
+ 0.15 × z(配当利回り)
+ 0.10 × z(自己株買い有無)
```

### 実行内容

1. PER、PBR、配当利回りを取得
2. ROE改善率、営業利益率改善率を計算
3. 自己株買い有無をEDINETまたはIRから取得
4. 可能であれば政策保有株縮減や中計ROE目標を手動補完
5. Transformation Scoreを算出
6. Moat Scoreと掛け合わせ、安いだけの企業を除外

### 実装計画

使用モジュール:

```text
src/data/build_fundamentals.py
src/screening/scoring.py
src/screening/select_candidates.py
```

出力:

```text
data/processed/transformation_scores.csv
data/processed/transformation_top.csv
```

### 求めるアウトカム

| 成果物 | 内容 |
|---|---|
| `transformation_scores.csv` | 変革余地スコア |
| `transformation_top.csv` | 変革余地上位企業 |
| レポート図表 | 変革余地の内訳表 |
| レポート本文 | 「ワイドモート×変革余地」の説明 |

---

## 2.6 第4スクリーニング：Future Moat Score

### 目的

AI時代に新しい堀が深まる企業を抽出する。

### 評価分類

| 分類 | 内容 |
|---|---|
| 計算資源の堀 | 半導体、製造装置、電子材料、検査装置 |
| インフラの堀 | データセンター、電力、光ファイバー、空調 |
| 現場実装の堀 | FA、ロボット、省人化、製造DX |
| データの堀 | SaaS、ERP、業務データ、医療・製造データ |
| 信頼の堀 | セキュリティ、監査、品質保証、ガバナンス |

### 使用式

```text
Future Moat Score_i
= 0.30 × AIInfrastructureExposure_i
+ 0.25 × IntangibleInvestment_i
+ 0.20 × AutomationExposure_i
+ 0.15 × DataSoftwareExposure_i
+ 0.10 × TrustSecurityExposure_i
```

キーワードスコア:

```text
Keyword Score_i = log(1 + keyword_count_i)
```

無形資産投資:

```text
IntangibleInvestment_i
= average_z(研究開発費率, ソフトウェア資産比率)
```

### 実行内容

1. EDINETの有報テキストを取得
2. 企業概要・事業等のリスク・研究開発活動などを抽出
3. Future Moat用キーワード辞書でスコアリング
4. 研究開発費率・ソフトウェア資産比率を取得
5. キーワードスコアと財務指標を統合
6. 最終候補についてはIR資料で定性確認

### 実装計画

使用モジュール:

```text
src/data/parse_edinet_xbrl.py
src/screening/future_moat_keywords.py
src/screening/scoring.py
```

出力:

```text
data/processed/future_moat_scores.csv
data/processed/future_moat_keyword_counts.csv
data/processed/future_moat_top.csv
```

### 求めるアウトカム

| 成果物 | 内容 |
|---|---|
| `future_moat_scores.csv` | AI時代の堀スコア |
| `future_moat_keyword_counts.csv` | キーワード出現数 |
| `future_moat_top.csv` | Future Moat上位企業 |
| レポート本文 | AI時代の堀を5分類で説明 |
| レポート図表 | Future Moatの分類別分布 |

---

## 2.7 第5スクリーニング：統合スコアと最終選定

### 使用式

```text
BEYOND BUFFETT Score_i
= 0.30 × Moat Score_i
+ 0.25 × Transformation Score_i
+ 0.30 × Future Moat Score_i
+ 0.15 × Valuation Score_i
```

補助的にモメンタムとリスクを加味する。

```text
Momentum Score_i
= z(過去12か月リターン - 直近1か月リターン)
```

```text
Risk Score_i
= average_z(過去3年ボラティリティ, 最大ドローダウン, 財務レバレッジ)
```

```text
Adjusted BB Score_i
= BEYOND BUFFETT Score_i
+ 0.10 × Momentum Score_i
- 0.10 × Risk Score_i
```

### 実行内容

1. 全スコアを統合
2. Adjusted BB Scoreを算出
3. 上位80社を候補化
4. セクター、時価総額、リスク、データ欠損を確認
5. 約20社に絞り込み
6. 各社にカテゴリを付与
   - Core Moat
   - Transformation Moat
   - Future Moat
   - Discovery

### 実装計画

使用モジュール:

```text
src/screening/scoring.py
src/screening/select_candidates.py
```

出力:

```text
data/processed/scores.csv
data/processed/candidates_top80.csv
data/processed/final_candidates.csv
data/processed/screening_summary.csv
```

### 求めるアウトカム

| 成果物 | 内容 |
|---|---|
| `scores.csv` | 全企業の総合スコア |
| `candidates_top80.csv` | 上位80社 |
| `final_candidates.csv` | 最終20社 |
| `screening_summary.csv` | 各段階の通過社数 |
| レポート図表 | スクリーニングフロー図 |
| レポート本文 | なぜ20社が選ばれたかの説明 |

---

# Ⅲ ポートフォリオ決定

# 1. ポートフォリオ配分・銘柄紹介

## 1.1 章の目的

この章の目的は、スクリーニングによって選定した20銘柄を、500万円の仮想資金でどのように配分するかを説明することである。

優秀レポートでは、最終銘柄を単純に等金額で買うのではなく、独自スコアや時価総額を用いて投資比率を決定している。本レポートでも、BEYOND BUFFETT Scoreを基準にしつつ、流動性・リスク・分散を考慮した配分を行う。

---

## 1.2 実行計画

### 前提条件

| 項目 | 内容 |
|---|---|
| 投資額 | 5,000,000円 |
| 銘柄数 | 約20銘柄 |
| 購入単位 | 1株単位 |
| 株価 | 前営業日終値 |
| 配分方法 | Adjusted BB Score加重 |
| 1銘柄上限 | 原則8% |
| 小型株 | 採用価値がある場合のみ、比率制限 |
| 金融銘柄 | 採用理由を明記 |

---

## 1.3 配分式

まず、スコアを正の値に変換する。

```text
Positive Score_i = max(Adjusted BB Score_i, 0)
```

基礎配分比率を算出する。

```text
Raw Weight_i = Positive Score_i / Σ Positive Score_j
```

1銘柄上限を適用する。

```text
Capped Weight_i = min(Raw Weight_i, 8%)
```

再正規化する。

```text
Final Weight_i = Capped Weight_i / Σ Capped Weight_j
```

投資予定額:

```text
Target Investment_i = 5,000,000 × Final Weight_i
```

株数:

```text
Shares_i = floor(Target Investment_i / Previous Close_i)
```

実投資額:

```text
Actual Investment_i = Shares_i × Previous Close_i
```

残現金:

```text
Cash = 5,000,000 - Σ Actual Investment_i
```

余剰現金は、スコア上位かつ1株価格が残現金以下の銘柄へ追加配分する。

---

## 1.4 カテゴリ配分

最終20銘柄は、以下の4分類に分ける。

| カテゴリ | 目安比率 | 役割 |
|---|---:|---|
| Core Moat | 30〜35% | 安定収益と下落耐性 |
| Transformation Moat | 25〜30% | 資本効率改善による再評価 |
| Future Moat | 30〜35% | AI時代の成長取り込み |
| Discovery | 5〜10% | 市場が見落とす高期待銘柄 |

---

## 1.5 銘柄紹介の型

各銘柄について、以下の型で紹介する。

```text
企業名：
コード：
市場区分：
業種：
カテゴリ：
投資比率：
投資金額：
株数：

事業概要：
選定理由：
既存Moat：
変革余地：
Future Moat：
期待シナリオ：
主なリスク：
ポートフォリオ内の役割：
```

### 銘柄紹介で求める水準

単なる企業概要ではなく、以下を必ず入れる。

1. なぜこの企業がBEYOND BUFFETT企業なのか
2. Moat・Transformation・Future Moatのどれが強いのか
3. どのようなシナリオで企業価値が上がるのか
4. どのリスクがあるのか
5. ポートフォリオ全体の中で何の役割を担うのか

---

## 1.6 実装計画

### 使用モジュール

```text
src/portfolio/allocate.py
src/report/tables.py
src/report/generate_markdown.py
```

### 入力ファイル

```text
final_candidates.csv
scores.csv
latest_prices.csv
```

### 出力ファイル

```text
portfolio.csv
portfolio_table.csv
category_allocation.csv
sector_allocation.csv
```

### `portfolio.csv` のカラム

```text
code
ticker
company_name
market
sector
category
adjusted_bb_score
previous_close
shares
actual_investment
weight
selection_reason
main_risk
```

---

## 1.7 求めるアウトカム

| アウトカム | 内容 |
|---|---|
| 500万円配分表 | 実際に何株買うかまで示す |
| 配分式 | 感覚ではなく数式で説明する |
| カテゴリ別比率 | 投資思想が見える |
| セクター別比率 | 偏りを可視化する |
| 銘柄紹介 | 20社それぞれの採用理由を説明 |
| 残現金 | 500万円に対する未使用額を明示 |

---

# 2. パフォーマンス分析

## 2.1 章の目的

パフォーマンス分析の目的は、構築したポートフォリオが、TOPIXや日経平均と比較してどのようなリターン・リスク特性を持つかを検証することである。

ここで重要なのは、単に「リターンが高かった」と示すことではない。優秀レポートのように、累積リターン、CAGR、ボラティリティ、シャープレシオ、最大ドローダウン、β、α、寄与度を示し、強みと弱みを正直に分析する。

---

## 2.2 実行計画

### 分析期間

原則として過去5年。  
ただし、最終銘柄に上場期間が短い企業が含まれる場合は、以下のどちらかを採用する。

| 方法 | 内容 |
|---|---|
| 共通期間方式 | 全銘柄の株価が揃う期間で分析 |
| 代替方式 | 上場期間が短い銘柄を除いた参考分析も併記 |

### ベンチマーク

| ベンチマーク | ticker | 理由 |
|---|---|---|
| TOPIX連動ETF | 1306.T | 実際に投資可能な市場平均proxy |
| 日経平均 | ^N225 または 1321.T | 国内代表指数との比較 |

---

## 2.3 使用式

### 日次リターン

```text
r_i,t = P_i,t / P_i,t-1 - 1
```

### ポートフォリオリターン

```text
r_p,t = Σ w_i × r_i,t
```

### 累積リターン

```text
Cumulative Return_T = Π(1 + r_p,t) - 1
```

### 年率リターン

```text
Annualized Return = (1 + Cumulative Return)^(252 / N) - 1
```

### 年率ボラティリティ

```text
Annualized Volatility = std(r_p,t) × √252
```

### シャープレシオ

```text
Sharpe Ratio = (Annualized Return - Risk Free Rate) / Annualized Volatility
```

初期分析では、Risk Free Rate = 0 とする。最終版では、0%仮定であることを明記する。

### 最大ドローダウン

```text
Portfolio Value_t = Π(1 + r_p,t)
```

```text
Drawdown_t = Portfolio Value_t / max(Portfolio Value_0 ... Portfolio Value_t) - 1
```

```text
Maximum Drawdown = min(Drawdown_t)
```

### CAPM α・β

```text
r_p,t - r_f,t = α + β(r_m,t - r_f,t) + ε_t
```

### Information Ratio

```text
Active Return_t = r_p,t - r_b,t
```

```text
Information Ratio = mean(Active Return_t) / std(Active Return_t) × √252
```

### 銘柄別寄与度

```text
Contribution_i = Weight_i × Cumulative Return_i
```

---

## 2.4 分析項目

| 分析 | 目的 |
|---|---|
| 累積リターン比較 | 市場平均を上回ったかを見る |
| CAGR | 長期的な成長力を見る |
| 年率ボラティリティ | 価格変動リスクを見る |
| シャープレシオ | リスク対比リターンを見る |
| 最大ドローダウン | 下落耐性を見る |
| β | 市場感応度を見る |
| α | 市場要因では説明できない超過リターンを見る |
| Information Ratio | ベンチマークを安定して上回ったかを見る |
| 銘柄別寄与度 | どの銘柄が成果に効いたかを見る |
| セクター寄与度 | 特定業種依存を確認する |

---

## 2.5 実装計画

### 使用モジュール

```text
src/portfolio/backtest.py
src/portfolio/metrics.py
src/report/charts.py
src/report/tables.py
```

### 入力ファイル

```text
portfolio.csv
prices_daily.parquet
benchmark_prices.parquet
```

### 出力ファイル

```text
portfolio_returns.csv
benchmark_returns.csv
performance_summary.csv
contribution_by_stock.csv
```

### 出力図表

```text
cumulative_return.png
drawdown.png
risk_return_scatter.png
contribution_by_stock.png
sector_allocation.png
category_allocation.png
```

---

## 2.6 求めるアウトカム

| アウトカム | 内容 |
|---|---|
| 累積リターン図 | PF、TOPIX、日経平均の比較 |
| ドローダウン図 | 下落局面での弱さを可視化 |
| 指標表 | CAGR、ボラ、シャープ、最大DD、α、β |
| 寄与度表 | リターンに効いた銘柄を示す |
| リスク分析本文 | 高リターンがリスクに見合うかを説明 |
| 弱点の明示 | 半導体偏重、景気敏感性、為替リスク等 |
| 結論 | テーマの有効性と限界を述べる |

---

# 3. Codex実装タスク一覧

## 3.1 スクリーニング実装

```text
src/data/load_jpx.py
src/data/fetch_yfinance.py
src/data/fetch_edinet.py
src/data/parse_edinet_xbrl.py
src/screening/scoring.py
src/screening/select_candidates.py
```

## 3.2 ポートフォリオ配分実装

```text
src/portfolio/allocate.py
```

## 3.3 パフォーマンス分析実装

```text
src/portfolio/backtest.py
src/portfolio/metrics.py
src/report/charts.py
```

## 3.4 レポート出力実装

```text
src/report/tables.py
src/report/generate_markdown.py
src/report/generate_docx.py
```

---

# 4. レポートにおける最終的な見せ方

## 4.1 Ⅱスクリーニングで載せる図表

| 図表 | 内容 |
|---|---|
| 図表1 | スクリーニング全体フロー |
| 図表2 | 各段階の通過社数 |
| 図表3 | BEYOND BUFFETT Scoreの構成 |
| 図表4 | Moat Score上位企業 |
| 図表5 | Transformation Score上位企業 |
| 図表6 | Future Moat Score上位企業 |
| 図表7 | 最終20社一覧 |

## 4.2 Ⅲ-1 ポートフォリオ配分・銘柄紹介で載せる図表

| 図表 | 内容 |
|---|---|
| 図表8 | 投資配分式 |
| 図表9 | 500万円配分表 |
| 図表10 | カテゴリ別投資比率 |
| 図表11 | セクター別投資比率 |
| 図表12 | 銘柄紹介表 |

## 4.3 Ⅲ-2 パフォーマンス分析で載せる図表

| 図表 | 内容 |
|---|---|
| 図表13 | 累積リターン比較 |
| 図表14 | ドローダウン推移 |
| 図表15 | 主要パフォーマンス指標 |
| 図表16 | 銘柄別寄与度 |
| 図表17 | リスク・リターン散布図 |
| 図表18 | 分析結果のまとめ |

---

# 5. 最終成果物チェックリスト

## スクリーニング

- [ ] 東証上場企業全体を母集団化
- [ ] ETF/REIT等を除外
- [ ] 各段階の通過社数を記録
- [ ] Moat Scoreを算出
- [ ] Transformation Scoreを算出
- [ ] Future Moat Scoreを算出
- [ ] Valuation Scoreを算出
- [ ] Adjusted BB Scoreを算出
- [ ] 最終20社を決定

## ポートフォリオ配分・銘柄紹介

- [ ] 前営業日終値を取得
- [ ] 500万円以内に収める
- [ ] 1株単位で株数を算出
- [ ] 1銘柄上限を設定
- [ ] カテゴリ別比率を算出
- [ ] セクター別比率を算出
- [ ] 20社の選定理由を作成

## パフォーマンス分析

- [ ] 過去5年株価を取得
- [ ] TOPIX・日経平均を取得
- [ ] 累積リターンを計算
- [ ] CAGRを計算
- [ ] 年率ボラを計算
- [ ] シャープレシオを計算
- [ ] 最大ドローダウンを計算
- [ ] α・βを計算
- [ ] Information Ratioを計算
- [ ] 銘柄別寄与度を計算
- [ ] 図表を生成

---

# 6. まとめ

本計画の要点は、以下の3点である。

1. **Ⅱスクリーニング**では、東証上場企業全体を対象に、Moat、Transformation、Future Moat、Valuationを数式化し、BEYOND BUFFETT企業を抽出する。

2. **Ⅲ-1 ポートフォリオ配分・銘柄紹介**では、Adjusted BB Scoreを用いて500万円を1株単位で配分し、各銘柄の役割をCore Moat、Transformation Moat、Future Moat、Discoveryに分類して説明する。

3. **Ⅲ-2 パフォーマンス分析**では、TOPIX・日経平均との比較を通じて、累積リターンだけでなく、CAGR、ボラティリティ、シャープレシオ、最大ドローダウン、α・β、寄与度まで検証し、テーマの有効性と限界を示す。

この流れにより、レポートは単なる銘柄紹介ではなく、**独自投資概念・定量スクリーニング・ポートフォリオ構築・実証分析が一貫した提出用レポート**として成立する。
