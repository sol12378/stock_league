# BEYOND BUFFETT 自動分析パイプライン計画書
## Codexを用いたデータ取得・スクリーニング・ポートフォリオ構成・分析の自動化

作成日: 2026-06-01  
対象プロジェクト: 日経STOCKリーグ提出レポート  
テーマ案: **BEYOND BUFFETT ——「完成された堀」から「進化する堀」へ——**

---

## 0. 本計画書の目的

本計画書は、日経STOCKリーグ提出レポートにおける以下の工程を、Codex・Python・公開データを用いて自動化するための実装計画である。

1. **データ取得の自動化**
   - 東証上場銘柄一覧
   - yfinanceによる株価・一部指標
   - EDINET APIによる有価証券報告書・XBRL取得

2. **スクリーニング**
   - 投資適格性
   - 既存Moat
   - 変革余地
   - Future Moat
   - バリュエーション規律

3. **500万円ポートフォリオ構成**
   - 前営業日終値ベース
   - 1株単位
   - 約20銘柄
   - スコア加重・リスク調整

4. **ポートフォリオ分析**
   - TOPIX・日経平均との比較
   - 累積リターン
   - 年率リターン
   - 年率ボラティリティ
   - シャープレシオ
   - 最大ドローダウン
   - CAPM α・β
   - セクター分散
   - 銘柄別寄与度

最終成果物は、レポート本文に挿入可能な **CSV・PNG図表・Markdown/Word草案** である。

---

## 1. 使用データ・ツール

### 1.1 データソース

| データ | 取得元 | 用途 | 備考 |
|---|---|---|---|
| 東証上場銘柄一覧 | JPX公式の上場銘柄一覧Excel | 母集団作成 | インストール済みファイルを使用 |
| 株価 | yfinance | 終値、過去株価、リターン分析 | 日本株は `7203.T` 形式 |
| TOPIX代替 | yfinance `1306.T` | TOPIX連動ETFとして比較 | 実際に投資可能なベンチマーク |
| 日経平均 | yfinance `^N225` またはETF | 日経平均比較 | `1321.T`も候補 |
| 有報・XBRL | EDINET API | 財務・非財務データ取得 | APIキーが必要 |
| 各社IR | 各社Webサイト | Future Moat・中計確認 | 最終候補の定性評価で使用 |
| IR BANK等 | 公開Web | 財務指標補助 | 自動取得は規約・負荷に注意 |

### 1.2 使用ライブラリ

```bash
python >= 3.11

pandas
numpy
requests
yfinance
lxml
beautifulsoup4
python-dotenv
tqdm
matplotlib
japanize-matplotlib
scipy
statsmodels
openpyxl
python-docx
pytest
ruff
mypy
```

### 1.3 Codexの役割

| 用途 | 内容 |
|---|---|
| 実装 | Pythonスクリプト生成 |
| リファクタリング | モジュール分割、エラー処理追加 |
| テスト生成 | pytest作成 |
| デバッグ | 取得失敗、欠損値、型エラー修正 |
| ドキュメント化 | README、実行手順、関数説明 |
| レポート補助 | 出力CSV・図表から本文草案を生成 |

重要方針:

- **数値計算はPythonで行う**
- **Codex/ChatGPTにはコード作成・文章化・チェックを任せる**
- **スクリーニング結果そのものをLLMの主観で決めない**
- **LLMによる定性評価は、最終候補企業のIR確認補助に限定する**

---

## 2. プロジェクト全体像

### 2.1 パイプライン概要

```text
JPX上場銘柄一覧
  ↓
universe.csv 作成
  ↓
yfinanceで株価取得
  ↓
EDINET APIで有報・XBRL取得
  ↓
財務指標テーブル作成
  ↓
Moat / Transformation / Future Moat / Valuation Score算出
  ↓
BEYOND BUFFETT Score算出
  ↓
上位候補80社抽出
  ↓
定性評価・セクター調整
  ↓
最終20銘柄決定
  ↓
昨日終値ベースで500万円配分
  ↓
過去3〜5年のバックテスト
  ↓
TOPIX・日経平均比較
  ↓
CSV・図表・レポート草案出力
```

### 2.2 推奨ディレクトリ構成

```text
beyond-buffett/
  README.md
  pyproject.toml
  .env.example
  requirements.txt

  data/
    raw/
      jpx/
        listed_companies.xlsx
      prices/
      edinet/
      ir/
    processed/
      universe.csv
      prices_daily.parquet
      fundamentals_raw.csv
      fundamentals_clean.csv
      scores.csv
      screening_summary.csv
      candidates_top80.csv
      portfolio.csv
      portfolio_returns.csv
      performance_summary.csv

  reports/
    figures/
      cumulative_return.png
      drawdown.png
      sector_allocation.png
      category_allocation.png
      score_distribution.png
      contribution_by_stock.png
      risk_return_scatter.png
    tables/
      screening_summary.csv
      portfolio_table.csv
      score_table.csv
      performance_summary.csv
    draft/
      report_draft.md
      beyond_buffett_report.docx

  src/
    __init__.py
    config.py
    run_all.py

    data/
      __init__.py
      load_jpx.py
      fetch_yfinance.py
      fetch_edinet.py
      parse_edinet_xbrl.py
      build_fundamentals.py
      cache.py

    screening/
      __init__.py
      universe_filter.py
      scoring.py
      future_moat_keywords.py
      select_candidates.py

    portfolio/
      __init__.py
      allocate.py
      backtest.py
      metrics.py

    report/
      __init__.py
      charts.py
      tables.py
      generate_markdown.py
      generate_docx.py

    utils/
      __init__.py
      dates.py
      logging.py
      validation.py

  prompts/
    codex_initial_implementation.md
    codex_debug.md
    company_qualitative_eval.md
    report_writer.md

  tests/
    test_scoring.py
    test_allocate.py
    test_metrics.py
    test_universe_filter.py
```

---

## 3. 環境構築

### 3.1 `.env.example`

```env
EDINET_API_KEY=your_edinet_api_key_here
JPX_LISTED_COMPANIES_PATH=data/raw/jpx/listed_companies.xlsx
BACKTEST_YEARS=5
TOTAL_CAPITAL=5000000
PORTFOLIO_SIZE=20
MAX_WEIGHT=0.08
TOPIX_PROXY=1306.T
NIKKEI=^N225
```

### 3.2 インストール

```bash
python -m venv .venv
source .venv/bin/activate

pip install -U pip
pip install pandas numpy requests yfinance lxml beautifulsoup4 python-dotenv tqdm matplotlib japanize-matplotlib scipy statsmodels openpyxl python-docx pytest ruff mypy
```

### 3.3 実行コマンド

最終的には、以下で全工程が走るようにする。

```bash
python -m src.run_all
```

部分実行も可能にする。

```bash
python -m src.data.load_jpx
python -m src.data.fetch_yfinance
python -m src.data.fetch_edinet
python -m src.screening.scoring
python -m src.portfolio.allocate
python -m src.portfolio.backtest
python -m src.report.charts
python -m src.report.generate_markdown
```

---

## 4. データ取得設計

## 4.1 東証上場銘柄一覧の読み込み

### 目的

東証全上場企業を母集団として、ETF・REIT・インフラファンド等を除外し、普通株を中心とした投資対象ユニバースを作る。

### 入力

```text
data/raw/jpx/listed_companies.xlsx
```

### 出力

```text
data/processed/universe.csv
```

### 主要カラム

```text
code
ticker
company_name
market
sector_33
sector_17
scale_category
is_financial
```

### 処理方針

1. Excelを読み込む
2. 証券コードを4桁文字列化
3. yfinance用tickerとして `.T` を付与
4. ETF、REIT、インフラファンド、優先株、外国株等を除外
5. 東証全市場を対象とする
6. 金融銘柄は除外せず、`is_financial` フラグを付与する
7. `universe.csv` に保存

### 金融銘柄の扱い

金融銘柄は、一般事業会社と財務構造が異なるため、ROICや自己資本比率などを同じ基準で比較しにくい。

- 金融銘柄は母集団に含める
- ただし、財務安全性やROIC評価では一般事業会社と別扱い
- 採用する場合は、選定理由を明確化する
- 例: 東京海上HDのように、収益力・グローバル展開・株主還元・リスク分散を説明できる企業

---

## 4.2 yfinanceによる株価取得

### 目的

以下を取得する。

- 前営業日終値
- 過去3〜5年の日次株価
- 分析用リターン
- 一部のPER、PBR、配当利回り等

### 入力

```text
data/processed/universe.csv
```

### 出力

```text
data/processed/prices_daily.parquet
data/processed/latest_prices.csv
```

### 対象ticker例

```text
7203.T
6758.T
8035.T
1306.T
^N225
```

### 取得項目

```text
date
ticker
open
high
low
close
adj_close
volume
```

### 実装上の注意

- yfinanceは取得失敗が起こるため、リトライ処理を入れる
- 一括取得は数百銘柄ずつに分割する
- rawデータはキャッシュ保存する
- 取得日・取得時刻をログに残す
- 前営業日終値は `latest_prices.csv` に保存する
- 配当調整済みリターンを使う場合は `Adj Close` を優先する
- 日本株は出来高が極端に低い銘柄があるため、流動性フィルターで除外する

---

## 4.3 EDINET APIによる有報・XBRL取得

### 目的

yfinanceだけでは不足する財務データを、EDINET APIで補完する。

### 取得対象

- 有価証券報告書
- 四半期報告書は原則不要
- 訂正報告書は初期段階では除外
- 最終候補・上位候補について重点的に取得

### EDINET APIの基本方針

1. 日付指定で提出書類一覧を取得
2. `docTypeCode` で有価証券報告書を抽出
3. `secCode` と証券コードを紐付け
4. `docID` を使ってXBRL zipを取得
5. XBRLを解凍・解析
6. 必要な財務項目を抽出
7. `fundamentals_raw.csv` に保存

### 代表的に抽出したい項目

```text
売上高
営業利益
経常利益
当期純利益
総資産
純資産
自己資本
営業キャッシュフロー
投資キャッシュフロー
財務キャッシュフロー
研究開発費
設備投資額
従業員数
セグメント売上
セグメント利益
配当総額
自己株式取得額
```

### XBRLタグの揺れへの対応

EDINET XBRLでは企業・会計基準・年度によってタグ名が異なる可能性がある。  
そのため、以下のように候補タグを複数持つ。

```python
TAG_CANDIDATES = {
    "revenue": ["NetSales", "Revenue", "OperatingRevenue1", "SalesRevenue"],
    "operating_income": ["OperatingIncome", "OperatingProfit"],
    "net_income": ["ProfitLossAttributableToOwnersOfParent", "NetIncome"],
    "total_assets": ["Assets", "TotalAssets"],
    "equity": ["Equity", "NetAssets"],
}
```

### EDINET取得の優先順位

全社のEDINET取得は重いため、段階的に行う。

| 段階 | 対象 | 理由 |
|---|---|---|
| Stage 1 | 全銘柄 | yfinance・JPXベースで粗くスクリーニング |
| Stage 2 | 上位300社 | EDINETで主要財務を補完 |
| Stage 3 | 上位80社 | 有報・中計・IRを詳しく確認 |
| Stage 4 | 最終20社 | XBRL・IR・定性評価を手厚く確認 |

---

## 5. スクリーニング設計

## 5.1 スクリーニング全体

```text
東証全上場企業
  ↓ 第1スクリーニング: 投資適格性
約1,500〜2,500社
  ↓ 第2スクリーニング: 既存Moat
約300〜500社
  ↓ 第3スクリーニング: 変革余地
約100〜200社
  ↓ 第4スクリーニング: Future Moat
約80社
  ↓ 第5スクリーニング: 定性評価・分散調整
最終20社程度
```

通過社数は実データ取得後に確定する。

---

## 5.2 第1スクリーニング: 投資適格性

### 目的

財務・流動性・分析可能性の観点から、明らかに投資対象として不適切な企業を除外する。

### 条件案

| 条件 | 内容 |
|---|---|
| 普通株であること | ETF・REIT・インフラファンド等を除外 |
| 株価取得可能 | yfinanceで直近終値が取得できる |
| 過去株価データあり | 最低3年、理想は5年 |
| 流動性 | 直近60営業日の平均売買代金が一定以上 |
| 財務危険除外 | 債務超過、極端な継続赤字を除外 |
| 異常値除外 | 株価、出来高、指標が極端に異常なものを除外 |

### 流動性指標

```text
平均売買代金_i = mean(Close_i,t × Volume_i,t)
```

### 欠損対応

- 主要指標が欠損している企業は一旦保留
- 銘柄として魅力がある場合はEDINET・IRで手動補完
- 欠損が多すぎる企業は除外

---

## 5.3 第2スクリーニング: 既存Moat Score

### 目的

バフェット型投資の中核である「既存の競争優位」を定量化する。

### 参考思想

Quality Minus Junk型のQuality概念を参考にする。  
高品質企業を、収益性・成長性・安全性・株主還元等の複合指標で評価する考え方である。

### 標準化

各指標はz-score化する。

```text
z(x_i) = (x_i - mean(x)) / std(x)
```

外れ値対策として、上下1%または5%でwinsorizeする。

```text
x_i^* = min(max(x_i, P1), P99)
```

### Moat Score

```text
Moat Score_i
= 0.35 × Profitability_i
+ 0.25 × CashGeneration_i
+ 0.20 × Stability_i
+ 0.20 × CompetitivePosition_i
```

### 構成要素

```text
Profitability_i
= average_z(営業利益率, ROE, ROIC)

CashGeneration_i
= average_z(営業CFマージン, FCFマージン)

Stability_i
= average_z(-営業利益率標準偏差, -売上成長率標準偏差)

CompetitivePosition_i
= average_z(粗利率, 研究開発費率, 海外売上比率)
```

### 無料データで取得困難な項目

| 項目 | 対応 |
|---|---|
| 粗利率 | 取得できれば使用。困難なら営業利益率で代替 |
| ROIC | NOPATと投下資本から推計 |
| 海外売上比率 | 最終候補のみ有報で確認 |
| 研究開発費率 | EDINETで取得。欠損時は0ではなく欠損扱い |

---

## 5.4 第3スクリーニング: Transformation Score

### 目的

「ワイドモートに変革余地を加える」ため、日本企業の資本効率改善・株主還元・再評価余地を評価する。

### 参考思想

Piotroski F-Scoreやバリュー投資の考え方を参考にする。  
ただし、単なる低PBR企業の抽出ではなく、日本企業改革の文脈に合わせて拡張する。

### Transformation Score

```text
Transformation Score_i
= 0.35 × ValuationGap_i
+ 0.25 × CapitalEfficiencyImprovement_i
+ 0.20 × ShareholderReturn_i
+ 0.20 × ReformEvidence_i
```

### 構成要素

```text
ValuationGap_i
= average_z(1/PBR, 1/PER, 1/EV_EBITDA)

CapitalEfficiencyImprovement_i
= average_z(ROE改善率, ROIC改善率, 営業利益率改善率)

ShareholderReturn_i
= average_z(配当利回り, 総還元性向, 自己株買い比率)

ReformEvidence_i
= average_z(中計ROE目標有無, 自己株買い有無, 政策保有株縮減有無)
```

### 初期実装版

無料データで安定的に取れる項目から始める。

```text
Transformation Score_i
= 0.35 × z(1/PBR)
+ 0.20 × z(1/PER)
+ 0.20 × z(ROE改善率)
+ 0.15 × z(配当利回り)
+ 0.10 × z(自己株買い有無)
```

### 注意点

- PBRやPERが欠損・マイナスの場合は慎重に扱う
- 赤字企業のPERは無意味なため欠損扱い
- 低PBRだが事業が弱い企業を拾わないよう、Moat Scoreと組み合わせる
- 金融銘柄はPBRやROEの意味が異なるため別評価にする

---

## 5.5 第4スクリーニング: Future Moat Score

### 目的

AI時代に「これから堀が深まる企業」を評価する。

### Future Moatの5分類

| 分類 | 内容 | 例 |
|---|---|---|
| 計算資源の堀 | 半導体・製造装置・材料・検査 | 半導体装置、電子材料 |
| インフラの堀 | データセンター・電力・通信・光ファイバー | 電線、空調、電力設備 |
| 現場実装の堀 | FA・ロボット・製造DX | 制御機器、産業ロボット |
| データの堀 | 業務データ・SaaS・医療データ | ERP、医療IT、業務SaaS |
| 信頼の堀 | セキュリティ・監査・品質保証 | サイバーセキュリティ、検査 |

### Future Moat Score

```text
Future Moat Score_i
= 0.30 × AIInfrastructureExposure_i
+ 0.25 × IntangibleInvestment_i
+ 0.20 × AutomationExposure_i
+ 0.15 × DataSoftwareExposure_i
+ 0.10 × TrustSecurityExposure_i
```

### キーワードスコア

各社の事業概要、決算説明資料、中期経営計画、有報テキストからキーワードを抽出する。

```text
KeywordScore_i = log(1 + keyword_count_i)
```

### キーワード辞書案

```python
KEYWORDS = {
    "ai_infrastructure": [
        "半導体", "生成AI", "AI", "GPU", "HBM", "データセンター",
        "光ファイバー", "電力", "電源", "空調", "サーバー"
    ],
    "automation": [
        "FA", "ロボット", "自動化", "省人化", "制御機器",
        "スマートファクトリー", "製造DX"
    ],
    "data_software": [
        "SaaS", "クラウド", "ERP", "業務データ", "DX",
        "データ分析", "AIエージェント"
    ],
    "trust_security": [
        "サイバーセキュリティ", "認証", "監査", "品質保証",
        "ガバナンス", "リスク管理", "ゼロトラスト"
    ]
}
```

### 注意点

- キーワード出現数だけで銘柄を決めない
- 最終候補は必ずIR・有報を確認する
- AIと無関係な文脈での「AI」連呼を除外する
- 半導体関連に偏りすぎないようセクター制約を入れる

---

## 5.6 Valuation Score

### 目的

高値掴みを避ける。  
AI関連・優良企業は高く評価されやすいため、バリュエーション規律を残す。

### Valuation Score

```text
Valuation Score_i
= 0.40 × z(1/PER)
+ 0.30 × z(1/PBR)
+ 0.20 × z(1/EV_EBITDA)
+ 0.10 × z(配当利回り)
```

初期実装ではEV/EBITDAが取れない場合があるため、以下で代替する。

```text
Valuation Score_i
= 0.50 × z(1/PER)
+ 0.35 × z(1/PBR)
+ 0.15 × z(配当利回り)
```

---

## 5.7 最終 BEYOND BUFFETT Score

### 基本式

```text
BEYOND BUFFETT Score_i
= 0.30 × Moat Score_i
+ 0.25 × Transformation Score_i
+ 0.30 × Future Moat Score_i
+ 0.15 × Valuation Score_i
```

AI比重は「強め〜中程度」とするため、Future Moatを30%にする。

### リスク調整後スコア

```text
Adjusted BB Score_i
= BEYOND BUFFETT Score_i
+ 0.10 × Momentum Score_i
- 0.10 × Risk Score_i
```

### Momentum Score

```text
Momentum Score_i
= z(過去12か月リターン - 直近1か月リターン)
```

### Risk Score

```text
Risk Score_i
= average_z(過去3年ボラティリティ, 最大ドローダウン, 財務レバレッジ)
```

### 最終採用方針

| 制約 | 内容 |
|---|---|
| 銘柄数 | 20銘柄程度 |
| 1銘柄上限 | 8%程度 |
| 小型株 | 採用価値がある場合のみ、比率制限 |
| 金融銘柄 | 説明可能な場合のみ採用 |
| 半導体集中 | 過度な集中を避ける |
| 欠損多い企業 | 原則除外、ただし重要銘柄は手動補完 |

---

## 6. ポートフォリオ構成

## 6.1 基本方針

- 投資額: 5,000,000円
- 銘柄数: 約20銘柄
- 株数: 1株単位
- 株価: 前営業日終値
- 配分: Adjusted BB Scoreに基づくスコア加重
- 1銘柄上限: 原則8%
- 余剰現金: スコア上位かつ購入可能な銘柄へ再配分

## 6.2 カテゴリ配分

| カテゴリ | 目安比率 | 役割 |
|---|---:|---|
| Core Moat | 30〜35% | 安定収益・複利成長 |
| Transformation Moat | 25〜30% | 日本株改革・再評価 |
| Future Moat | 30〜35% | AI時代の成長 |
| Discovery | 5〜10% | 市場の見落とし |

## 6.3 配分式

```text
PositiveScore_i = max(Adjusted BB Score_i, 0)
RawWeight_i = PositiveScore_i / Σ PositiveScore_j
CappedWeight_i = min(RawWeight_i, MaxWeight)
FinalWeight_i = CappedWeight_i / Σ CappedWeight_j
TargetInvestment_i = TotalCapital × FinalWeight_i
Shares_i = floor(TargetInvestment_i / PreviousClose_i)
ActualInvestment_i = Shares_i × PreviousClose_i
Cash = TotalCapital - Σ ActualInvestment_i
```

余剰現金は、以下の条件を満たす銘柄へ1株ずつ追加する。

1. FinalWeightに対して実投資額が不足している
2. 1株価格が余剰現金以下
3. 1銘柄上限を超えない
4. Adjusted BB Scoreが高い

---

## 7. ポートフォリオ分析

## 7.1 分析期間

- 原則: 過去5年
- 上場期間が短い銘柄を含む場合: 共通取得期間または3年に短縮
- ベンチマーク: TOPIX連動ETF `1306.T`、日経平均 `^N225` または `1321.T`

## 7.2 日次リターン

```text
r_i,t = P_i,t / P_i,t-1 - 1
```

調整後終値が取得できる場合は `Adj Close` を使用する。

## 7.3 ポートフォリオリターン

```text
r_p,t = Σ w_i × r_i,t
```

ここで `w_i` は初期投資比率とする。  
厳密なリバランスは行わず、初期投資後のバイ・アンド・ホールドを基本とする。

## 7.4 累積リターン

```text
CumulativeReturn_T = Π(1 + r_p,t) - 1
```

## 7.5 年率リターン

```text
AnnualizedReturn = (1 + CumulativeReturn)^(252 / N) - 1
```

## 7.6 年率ボラティリティ

```text
AnnualizedVolatility = std(r_p,t) × sqrt(252)
```

## 7.7 シャープレシオ

```text
SharpeRatio = (AnnualizedReturn - RiskFreeRate) / AnnualizedVolatility
```

初期実装では `RiskFreeRate = 0` とする。  
最終版では日本の短期金利を使うか、0%仮定と明記する。

## 7.8 最大ドローダウン

```text
PortfolioValue_t = Π(1 + r_p,t)
RunningMax_t = max(PortfolioValue_0, ..., PortfolioValue_t)
Drawdown_t = PortfolioValue_t / RunningMax_t - 1
MaximumDrawdown = min(Drawdown_t)
```

## 7.9 CAPM α・β

```text
r_p,t - r_f,t = α + β(r_m,t - r_f,t) + ε_t
```

- `r_p,t`: ポートフォリオ日次リターン
- `r_m,t`: TOPIX連動ETFまたは日経平均の日次リターン
- `r_f,t`: リスクフリーレート
- `α`: 市場では説明できない超過リターン
- `β`: 市場感応度

## 7.10 Information Ratio

```text
ActiveReturn_t = r_p,t - r_b,t
InformationRatio = mean(ActiveReturn_t) / std(ActiveReturn_t) × sqrt(252)
```

## 7.11 銘柄別寄与度

```text
Contribution_i = Weight_i × CumulativeReturn_i
```

## 7.12 セクター・カテゴリ分析

出力する分析:

- 業種別投資比率
- カテゴリ別投資比率
  - Core Moat
  - Transformation Moat
  - Future Moat
  - Discovery
- 時価総額規模別比率
- 金融銘柄比率
- AI関連比率
- 半導体関連比率

---

## 8. 出力ファイル

### 8.1 CSV

```text
data/processed/universe.csv
data/processed/latest_prices.csv
data/processed/fundamentals_clean.csv
data/processed/scores.csv
data/processed/screening_summary.csv
data/processed/candidates_top80.csv
data/processed/portfolio.csv
data/processed/portfolio_returns.csv
data/processed/performance_summary.csv
```

### 8.2 図表

```text
reports/figures/cumulative_return.png
reports/figures/drawdown.png
reports/figures/sector_allocation.png
reports/figures/category_allocation.png
reports/figures/score_distribution.png
reports/figures/contribution_by_stock.png
reports/figures/risk_return_scatter.png
```

### 8.3 レポート草案

```text
reports/draft/report_draft.md
reports/draft/beyond_buffett_report.docx
```

---

## 9. Codex実行計画

## 9.1 Codexに実装させる順序

一度に全部作らせず、以下の順番で分割する。

### Phase 1: プロジェクト骨格

目的:

- ディレクトリ作成
- 設定ファイル
- README
- logging
- config

Codexプロンプト:

```text
このリポジトリに、日経STOCKリーグ向けの日本株分析パイプラインの骨格を作成してください。

要件:
- Python 3.11想定
- src/配下にモジュール分割
- data/raw, data/processed, reports/figures, reports/tables, reports/draftを作成
- .env.exampleを作成
- config.pyで環境変数を読み込む
- loggingユーティリティを作成
- README.mdに実行手順を書く
- pytest, ruffを使える構成にする
```

### Phase 2: JPX銘柄一覧読み込み

Codexプロンプト:

```text
data/raw/jpx/listed_companies.xlsx を読み込み、東証上場企業の母集団 universe.csv を作成する src/data/load_jpx.py を実装してください。

要件:
- 証券コードを4桁文字列に変換
- ticker列として .T を付ける
- ETF, REIT, インフラファンド, 優先株, 外国株を除外できるようにする
- 市場区分、業種、会社名を保持
- 金融銘柄には is_financial フラグを付ける
- 出力は data/processed/universe.csv
- 列名の揺れに強い実装にする
- pytestを作成する
```

### Phase 3: yfinance株価取得

Codexプロンプト:

```text
universe.csv のticker列を使って、yfinanceから日本株の日次株価を取得する src/data/fetch_yfinance.py を実装してください。

要件:
- 過去5年の日次 OHLCV と Adj Close を取得
- 前営業日終値を latest_prices.csv に保存
- 全銘柄を一括取得せず、チャンク分割して取得
- 取得失敗銘柄を logs/failed_tickers.csv に保存
- リトライ処理を入れる
- TOPIX代替として 1306.T、日経平均として ^N225 も取得
- prices_daily.parquet に保存
```

### Phase 4: EDINET API取得

Codexプロンプト:

```text
EDINET APIを用いて、有価証券報告書の書類一覧取得とXBRLダウンロードを行う src/data/fetch_edinet.py を実装してください。

要件:
- .envから EDINET_API_KEY を読み込む
- 指定日範囲の documents.json を取得
- docTypeCodeで有価証券報告書を抽出
- secCodeとJPXの証券コードを紐付ける
- docIDごとにXBRL zipをダウンロード
- data/raw/edinet/ に保存
- 取得済みファイルは再取得しない
- レート制限を考慮してsleepを入れる
- 取得ログを残す
```

### Phase 5: EDINET XBRL解析

Codexプロンプト:

```text
EDINETから取得したXBRL zipを解析して、主要財務項目を抽出する src/data/parse_edinet_xbrl.py を実装してください。

要件:
- zipを解凍せずに読み込めるなら読み込む
- XBRL内のixbrl/html/xmlから主要タグを探す
- 売上高、営業利益、純利益、総資産、純資産、営業CF、研究開発費を抽出
- タグ名の揺れに対応するTAG_CANDIDATESを持つ
- 企業別・年度別に fundamentals_raw.csv を作成
- 取れなかった項目はNaNにする
- 解析失敗ファイルをログに残す
```

### Phase 6: スコアリング

Codexプロンプト:

```text
fundamentals_clean.csv, latest_prices.csv, prices_daily.parquet を用いて、BEYOND BUFFETT Scoreを計算する src/screening/scoring.py を実装してください。

要件:
- winsorize関数を実装
- z-score関数を実装
- Moat Scoreを計算
- Transformation Scoreを計算
- Future Moat Scoreを計算
- Valuation Scoreを計算
- Momentum ScoreとRisk Scoreを計算
- Adjusted BB Scoreを計算
- 金融銘柄は一部指標を別扱いにできる設計にする
- 出力は data/processed/scores.csv
- 欠損値があっても落ちない
- スコアの内訳を保存する
```

### Phase 7: 最終候補選定

Codexプロンプト:

```text
scores.csvを用いて、最終候補80社とポートフォリオ候補20社を選ぶ src/screening/select_candidates.py を実装してください。

要件:
- Adjusted BB Score上位80社を candidates_top80.csv に保存
- 20社候補を選ぶ
- セクター集中を制御する
- 1カテゴリに偏りすぎないようにする
- Core Moat, Transformation Moat, Future Moat, Discovery のカテゴリを付与
- 金融銘柄と小型株は採用理由を書くためのフラグを付ける
- portfolio_candidates.csvを出力
```

### Phase 8: 500万円配分

Codexプロンプト:

```text
portfolio_candidates.csvとlatest_prices.csvを使って、500万円を1株単位で配分する src/portfolio/allocate.py を実装してください。

要件:
- 総投資額は500万円
- 前営業日終値を使う
- 1株単位で株数を計算
- 1銘柄上限は8%
- Adjusted BB Scoreに基づいて加重配分
- 余剰現金をスコア上位銘柄に再配分
- 出力は data/processed/portfolio.csv
- 投資額、比率、残現金を出力
```

### Phase 9: バックテスト・分析

Codexプロンプト:

```text
portfolio.csvとprices_daily.parquetを使って、ポートフォリオの過去5年パフォーマンスを分析する src/portfolio/backtest.py と src/portfolio/metrics.py を実装してください。

要件:
- Adj Closeを使って日次リターンを計算
- 初期ウェイト固定のバイ・アンド・ホールドで計算
- TOPIX代替 1306.T、日経平均 ^N225 と比較
- 累積リターン、年率リターン、年率ボラ、シャープレシオ、最大ドローダウンを計算
- CAPM alpha/betaをstatsmodelsで計算
- Information Ratioを計算
- 銘柄別寄与度を計算
- 出力は portfolio_returns.csv と performance_summary.csv
```

### Phase 10: 図表生成

Codexプロンプト:

```text
分析結果CSVをもとに、日経STOCKリーグのレポートに使う図表を生成する src/report/charts.py を実装してください。

要件:
- matplotlibを使用
- 日本語フォントに対応
- 累積リターン比較
- ドローダウン推移
- セクター別投資比率
- カテゴリ別投資比率
- スコア分布
- 銘柄別寄与度
- リスク・リターン散布図
- reports/figures にPNG保存
```

### Phase 11: レポート草案出力

Codexプロンプト:

```text
CSVとPNGをもとに、日経STOCKリーグ提出用レポートの材料となるMarkdown草案を生成する src/report/generate_markdown.py を実装してください。

要件:
- screening_summary.csvの通過社数を本文に挿入
- portfolio.csvをMarkdown表として挿入
- performance_summary.csvをMarkdown表として挿入
- 図表のパスをMarkdownに挿入
- reports/draft/report_draft.md を出力
```

### Phase 12: 全工程実行

Codexプロンプト:

```text
これまで実装した全工程を python -m src.run_all で順番に実行できるようにしてください。

順序:
1. load_jpx
2. fetch_yfinance
3. fetch_edinet
4. parse_edinet_xbrl
5. build_fundamentals
6. scoring
7. select_candidates
8. allocate
9. backtest
10. charts
11. generate_markdown

要件:
- 各工程の開始・終了ログを出す
- 途中失敗時にどの工程で失敗したか分かるようにする
- 既存データを使って一部工程をskipできるようにする
- CLI引数で --skip-edinet, --skip-fetch-prices などを指定できるようにする
```

---

## 10. 品質管理・テスト

## 10.1 テスト対象

| テスト | 内容 |
|---|---|
| `test_zscore` | 標準化が正しいか |
| `test_winsorize` | 外れ値処理が正しいか |
| `test_allocate_sum` | 投資額が500万円以内か |
| `test_max_weight` | 1銘柄上限を超えていないか |
| `test_returns` | リターン計算が正しいか |
| `test_drawdown` | 最大ドローダウン計算が正しいか |
| `test_capm` | 回帰分析が落ちないか |
| `test_universe` | ETF/REIT除外が機能するか |

## 10.2 データ品質チェック

```text
- tickerが重複していないか
- 株価が0以下でないか
- 出来高が異常でないか
- PER/PBRの異常値を除外しているか
- 欠損率が高すぎる銘柄を除外しているか
- 最終20銘柄の全てに終値があるか
- portfolio.csvの投資額合計が500万円以下か
- ベンチマークデータが取得できているか
```

---

## 11. レポートへの反映方法

### 11.1 スクリーニング章に使う出力

| レポート要素 | 出力ファイル |
|---|---|
| 母集団数 | `screening_summary.csv` |
| 各段階通過社数 | `screening_summary.csv` |
| スコア上位企業 | `candidates_top80.csv` |
| 最終20社 | `portfolio.csv` |
| スコア分布図 | `score_distribution.png` |

### 11.2 ポートフォリオ章に使う出力

| レポート要素 | 出力ファイル |
|---|---|
| 500万円配分表 | `portfolio.csv` |
| 業種別比率 | `sector_allocation.png` |
| カテゴリ別比率 | `category_allocation.png` |
| 銘柄別投資額 | `portfolio_table.csv` |

### 11.3 分析章に使う出力

| レポート要素 | 出力ファイル |
|---|---|
| 累積リターン | `cumulative_return.png` |
| ドローダウン | `drawdown.png` |
| 指標表 | `performance_summary.csv` |
| 寄与度 | `contribution_by_stock.png` |
| リスク・リターン | `risk_return_scatter.png` |

---

## 12. 実装スケジュール案

### Day 1: 基盤構築

- ディレクトリ作成
- 環境構築
- JPX銘柄一覧読み込み
- universe.csv作成

### Day 2: 株価取得

- yfinance取得
- latest_prices.csv作成
- prices_daily.parquet作成
- TOPIX・日経平均取得

### Day 3: EDINET取得

- EDINET API接続
- 書類一覧取得
- 有報XBRLダウンロード
- 一部企業でXBRL解析テスト

### Day 4: スコアリング

- 財務指標整備
- z-score
- Moat Score
- Transformation Score
- Future Moat Score
- BB Score

### Day 5: ポートフォリオ構成

- 上位80社抽出
- 最終20社候補
- 500万円配分
- セクター調整

### Day 6: 分析

- バックテスト
- TOPIX・日経平均比較
- パフォーマンス指標計算
- 図表生成

### Day 7: レポート反映

- Markdown草案生成
- 図表・表の整理
- 手動で企業選定理由を追記
- docx化準備

---

## 13. リスクと対策

| リスク | 内容 | 対策 |
|---|---|---|
| yfinance取得失敗 | 一部銘柄の株価が取れない | リトライ、失敗リスト、手動補完 |
| EDINET解析困難 | XBRLタグが企業ごとに異なる | タグ候補辞書、上位候補のみ重点解析 |
| 財務指標欠損 | 無料データでは欠損が多い | 欠損率管理、IR資料で補完 |
| AI関連度が主観的 | キーワードだけでは不十分 | ChatGPTでIR要約、最終手動確認 |
| 半導体偏重 | AIテーマで偏りやすい | セクター上限・カテゴリ配分 |
| 小型株リスク | 流動性・ボラが高い | Discovery枠は5〜10%に制限 |
| 金融銘柄比較 | 財務指標が一般企業と異なる | 別評価・採用理由明記 |
| バックテストの生存者バイアス | 現在上場企業のみで過去比較 | レポートで限界として明記 |
| 無料データの基準日差 | 財務・株価のタイミングがズレる | 基準日を明記、最終候補は再確認 |

---

## 14. レポートに明記すべきデータ上の限界

最終レポートでは、以下のように書く。

```text
本分析では、無料・公開データを中心に用いたため、一部の財務指標やガバナンス指標については欠損や基準日の差異が存在する。そのため、一次スクリーニングでは取得可能な定量指標を用い、最終選定段階では各社の有価証券報告書、決算説明資料、中期経営計画を確認することで、データ上の限界を補完した。また、バックテストは現在上場している企業を対象としているため、上場廃止企業を含まない生存者バイアスが存在する可能性がある。
```

---

## 15. 最終成果物チェックリスト

### データ

- [ ] `universe.csv`
- [ ] `latest_prices.csv`
- [ ] `fundamentals_clean.csv`
- [ ] `scores.csv`
- [ ] `screening_summary.csv`
- [ ] `candidates_top80.csv`
- [ ] `portfolio.csv`
- [ ] `performance_summary.csv`

### 図表

- [ ] 累積リターン比較
- [ ] ドローダウン推移
- [ ] セクター別比率
- [ ] カテゴリ別比率
- [ ] スコア分布
- [ ] 銘柄別寄与度
- [ ] リスク・リターン散布図

### レポート材料

- [ ] スクリーニング通過社数
- [ ] 最終20社の選定理由
- [ ] 500万円配分表
- [ ] TOPIX・日経平均比較
- [ ] α・β
- [ ] リスク分析
- [ ] データ上の限界
- [ ] 参考文献・データ出所

---

## 16. 参考情報・公式ドキュメント

- JPX: List of TSE-listed Issues  
  https://www.jpx.co.jp/english/markets/statistics-equities/misc/01.html

- JPX: Listed Company Search  
  https://www.jpx.co.jp/english/listing/co-search/index.html

- yfinance Documentation  
  https://ranaroussi.github.io/yfinance/

- yfinance GitHub  
  https://github.com/ranaroussi/yfinance

- EDINET API 仕様書  
  https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf

- EDINET API案内  
  https://disclosure2.edinet-fsa.go.jp/week0020.aspx

- OpenAI Codex CLI Reference  
  https://developers.openai.com/codex/cli/reference

- OpenAI Codex Non-interactive Mode  
  https://developers.openai.com/codex/noninteractive

---

## 17. 最初にCodexへ投げる統合プロンプト

以下を最初のCodexプロンプトとして使用する。

```text
あなたはPythonによる金融データ分析パイプラインの実装担当です。
日経STOCKリーグ向けに、東証上場銘柄のデータ取得、スクリーニング、500万円ポートフォリオ構成、TOPIX・日経平均とのパフォーマンス比較を自動化するリポジトリを作成してください。

前提:
- 東証上場銘柄一覧Excelは data/raw/jpx/listed_companies.xlsx に配置済み
- 株価取得には yfinance を用いる
- 有価証券報告書取得には EDINET API を用いる
- EDINET_API_KEY は .env から読み込む
- 投資額は500万円
- 1株単位で購入可能
- 最終銘柄数は20銘柄程度
- 株価は前営業日終値を用いる
- ベンチマークは 1306.T と ^N225

実装方針:
- src/配下にモジュール分割する
- python -m src.run_all で全工程を実行できるようにする
- 各工程の出力は data/processed に保存する
- 図表は reports/figures に保存する
- レポート草案は reports/draft/report_draft.md に保存する
- 欠損値や取得失敗に強くする
- ログを残す
- pytestを作成する

スコア:
BEYOND BUFFETT Score
= 0.30 × Moat Score
+ 0.25 × Transformation Score
+ 0.30 × Future Moat Score
+ 0.15 × Valuation Score

必要な分析:
- 累積リターン
- 年率リターン
- 年率ボラティリティ
- シャープレシオ
- 最大ドローダウン
- CAPM alpha/beta
- Information Ratio
- 銘柄別寄与度
- セクター別比率
- カテゴリ別比率

まずはディレクトリ構成、README、config.py、load_jpx.py、fetch_yfinance.pyから実装してください。
```

---

## 18. 結論

本計画では、Codexを実装補助として用い、Pythonで以下を自動化する。

1. 東証上場銘柄一覧から母集団を作成する  
2. yfinanceで株価とベンチマークを取得する  
3. EDINET APIで有報・XBRLを取得する  
4. BEYOND BUFFETT Scoreで銘柄を点数化する  
5. 約20銘柄の500万円ポートフォリオを構成する  
6. TOPIX・日経平均と比較してパフォーマンスを検証する  
7. CSV・図表・レポート草案を自動生成する  

これにより、日経STOCKリーグのレポートにおいて、単なる主観的な銘柄選定ではなく、先行研究・定量指標・公開データ・リスク分析に基づく再現可能な投資戦略として提示できる。
