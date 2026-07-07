# BEYOND BUFFETT Phase1（守）実装プロンプト・参照式リファレンス

## 0. この文書の目的

この文書は、日経STOCKリーグ向けレポート「BEYOND BUFFETT」の **Phase1（守）** を、Codexで完遂するための実装指示書である。

Phase1の目的は、独自の重み付き評価式を作ることではない。  
目的は、**先行研究・査読論文・広く引用される実証研究で定義された式だけを用いて、公開データで再現可能な「バフェット型投資」を日本株で近似し、20銘柄の Buffett Proxy Portfolio を構築すること**である。

このPhase1は、後続の「破」「離」の土台になる。  
したがって、ここでは Future Moat、AI関連テキスト、資本効率改革テキスト、独自BEYOND BUFFETT Score は使わない。  
あくまで、現在観測可能な **Value × Quality × Profitability × Earnings Quality × Financial Strength × Low Distress** によって、「完成された堀」を持つ企業を抽出する。

---

## 1. Phase1の設計思想

### 1.1 Phase1は「完全なBuffett再現」ではなく「Buffett Proxy」

Buffettの実際の投資判断には、公開データだけでは再現できない要素が多い。

再現できないものの例：

- 経営者との対話
- 非公開企業買収
- 保険フロートによる低コストレバレッジ
- 税の繰延べ
- 交渉力
- 長期の関係資本
- 経営者評価
- 事業理解の深さ
- ガバナンス介入

したがってPhase1では、Buffettの実際のポートフォリオそのものを再現するのではなく、公開データで観測できる以下の要素に限定して近似する。

| Buffett型の要素 | 公開データ上の代理変数 |
|---|---|
| 良い会社 | Quality |
| 高収益企業 | Profitability |
| 現金を生む企業 | Cash Flow Quality / Earnings Quality |
| 財務的に安全な企業 | Financial Strength |
| 破綻しにくい企業 | Low Distress |
| 高すぎない価格 | Value |
| 長期保有に耐える企業 | Quality + Safety + Low Accruals |

このため、Phase1のポートフォリオは **Buffett Proxy Portfolio** と呼ぶ。

---

### 1.2 独自式を避ける理由

旧案では、たとえば以下のような独自合成式が考えられていた。

```text
MOAT = 0.35 PROF + 0.25 CF + 0.20 STAB + 0.20 COMP
```

しかし、Phase1は「守」であるため、独自係数を前面に出すべきではない。  
なぜなら、係数 `0.35, 0.25, 0.20, 0.20` の根拠が先行研究そのものに由来せず、審査員や先生から「なぜその重みなのか」と問われやすいからである。

Phase1では、以下のような研究由来の方法を優先する。

- 論文で定義された式
- 論文で定義された二値スコア
- 論文で使われる分位ソート
- 論文で使われる二重ソート
- 論文で定義された除外条件
- 検証指標としての古典的リスク・リターン指標

つまり、**独自に重みを決めるのではなく、先行研究に埋め込まれている式・合成法・ソート法をそのまま使う**。

---

### 1.3 Phase1で使う式・使わない式

#### Phase1で採用する式

| 区分 | 式・指標 | 役割 |
|---|---|---|
| Buffett研究 | Buffett’s Alpha | Phase1の理論背景 |
| Quality | Quality Minus Junk | 良い会社の代理変数 |
| Profitability | Gross Profitability | 収益エンジンの強さ |
| Value | B/M, E/P | 合理的価格 |
| Financial Strength | Piotroski F-Score | 財務健全性・改善 |
| Earnings Quality | Sloan Accruals | 会計利益の質 |
| Low Distress | Ohlson O-Score | 破綻リスク除外 |
| Low Distress | Altman Z-Score | 破綻リスク除外補助 |
| Validation | Markowitz Variance | ポートフォリオ分散検証 |
| Validation | Sharpe Ratio | リスク調整後リターン |
| Validation | Jensen’s Alpha | 市場要因控除後の超過収益 |

#### Phase1では使わない式

| 式・指標 | 理由 |
|---|---|
| 独自MOAT Score | Phase1では独自重みを避けるため |
| Transformation Score | 「変わる堀」でありPhase2以降 |
| Future Moat Score | 「生まれる堀」でありPhase3以降 |
| BEYOND BUFFETT Score | 独自統合式でありPhase1には不適 |
| Momentum Score | Buffett型の守の中心ではない |
| AI関連キーワードスコア | Future Moat要素でありPhase1では使わない |
| 政策保有株・中計テキスト分析 | Transformation要素でありPhase1では使わない |
| Markowitz最適化によるウェイト決定 | 期待収益率推定に恣意性が入りやすいため検証に限定 |

---

# 2. 参照式・参考文献まとめ

## 2.1 Buffett’s Alpha

### 文献

Frazzini, Andrea, David Kabiller, and Lasse H. Pedersen.  
“Buffett’s Alpha.” *Financial Analysts Journal*, 2018.

### 何を示した研究か

Buffettの長期的な超過リターンは、単なる市場リスクやサイズ効果だけでは説明できない。  
研究では、Buffettの成果の多くが以下で説明できるとされる。

- cheap stocks
- safe stocks
- high-quality stocks
- low-cost leverage
- 長期保有

Phase1で再現できるのは、主に **cheap / safe / high-quality stocks** の部分である。  
保険フロートや非公開企業買収は、日経STOCKリーグの公開データ分析では再現できない。

### Phase1での意味

Phase1の理論背景として最重要。  
「Buffett型投資は、公開データ上では Value × Quality × Safety として近似できる」という根拠になる。

### レポートでの使い方

本文では以下のように書ける。

> Buffettの投資を完全に再現することはできないが、Frazzini, Kabiller, Pedersen の研究に基づけば、その上場株投資の特徴は、割安で、安全で、高品質な株式への長期投資として近似できる。したがってPhase1では、公開財務データで観測可能な Value, Quality, Financial Strength, Low Distress に限定して、Buffett Proxy Portfolioを構築する。

---

## 2.2 Quality Minus Junk（QMJ）

### 文献

Asness, Clifford S., Andrea Frazzini, and Lasse H. Pedersen.  
“Quality Minus Junk.” *Review of Accounting Studies*, 2019.

### 式の概要

QMJでは、企業のQualityを以下の4分類で捉える。

```text
Quality = average(Profitability, Growth, Safety, Payout)
```

それぞれの構成要素は、複数の指標を順位化・標準化して合成する。

一般形：

```text
z(x_i) = (rank(x_i) - mean(rank(x))) / std(rank(x))
```

または、クロスセクション内のrank-z-scoreとして標準化する。

#### Profitabilityの例

```text
Profitability = average(
  z(Gross Profits / Assets),
  z(ROE),
  z(ROA),
  z(CFO / Assets),
  z(Gross Margin),
  z(-Accruals)
)
```

#### Growthの例

過去複数年の収益性・利益成長・売上成長などの安定的な改善を捉える。

#### Safetyの例

```text
Safety = average(
  z(-Beta),
  z(-Idiosyncratic Volatility),
  z(-Leverage),
  z(-Ohlson O-Score),
  z(Altman Z-Score),
  z(-Earnings Volatility)
)
```

#### Payoutの例

```text
Payout = average(
  z(Net Payout Yield),
  z(Equity Issuanceの少なさ),
  z(Debt Issuanceの少なさ)
)
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| Gross Profits / Assets | 総資産に対する粗利益 |
| ROE | 株主資本利益率 |
| ROA | 総資産利益率 |
| CFO / Assets | 総資産に対する営業キャッシュフロー |
| Gross Margin | 粗利率 |
| Accruals | 会計利益に含まれる発生主義部分 |
| Leverage | 財務レバレッジ |
| O-Score | Ohlson破綻リスク |
| Z-Score | Altman破綻安全性 |
| Net Payout Yield | 株主還元利回り |

### 何を意味するか

QMJは、「良い企業」を単一指標ではなく、以下の総合概念で捉える。

- 稼ぐ力がある
- 成長している
- 安全である
- 株主に還元する
- 会計利益の質が高い
- 倒産リスクが低い

### バフェット型投資との関係

Buffett型投資の「良い会社を買う」に最も近い。  
特に `safe, high-quality stocks` というBuffett’s Alphaの解釈と接続しやすい。

### Phase1での使い方

可能ならQMJ full versionを実装する。  
ただし、日本株3,299社で必要変数が揃わない場合は、勝手に独自簡略化しない。  
その場合は「QMJ full unavailable」と明記し、Gross Profitability、F-Score、Accruals、O-Scoreで代替する。

---

## 2.3 Gross Profitability

### 文献

Novy-Marx, Robert.  
“The Other Side of Value: The Gross Profitability Premium.” *Journal of Financial Economics*, 2013.

### 式

```text
GP_A = Gross Profit / Total Assets
```

または、

```text
GP_A = (Revenue - Cost of Goods Sold) / Total Assets
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| Revenue | 売上高 |
| Cost of Goods Sold | 売上原価 |
| Gross Profit | 粗利益 |
| Total Assets | 総資産 |

### 何を意味するか

企業が総資産を使ってどれだけ粗利益を生み出しているかを測る。

営業利益や純利益よりも上流の収益力を見るため、

- 価格決定力
- 商品・サービスの付加価値
- 事業モデルの強さ
- 総資産に対する収益エンジン

を測りやすい。

### バフェット型投資との関係

Buffett型の「堀」は、長期的な価格決定力や高い収益性として財務諸表に現れる。  
Gross Profitabilityは、その堀を最も単純に測る代理変数である。

### Phase1での使い方

Quality screenの中核に置く。  
非金融業を対象に、Gross Profitabilityが市場中央値以上、または上位分位の銘柄を優先する。

---

## 2.4 Fama-French 3 Factor / 5 Factor

### 文献

Fama, Eugene F., and Kenneth R. French.  
“Common Risk Factors in the Returns on Stocks and Bonds.” *Journal of Financial Economics*, 1993.

Fama, Eugene F., and Kenneth R. French.  
“A Five-Factor Asset Pricing Model.” *Journal of Financial Economics*, 2015.

### 3ファクターモデル

```text
R_i,t - R_f,t
= α_i
+ β_i (R_M,t - R_f,t)
+ s_i SMB_t
+ h_i HML_t
+ ε_i,t
```

### 5ファクターモデル

```text
R_i,t - R_f,t
= α_i
+ β_i (R_M,t - R_f,t)
+ s_i SMB_t
+ h_i HML_t
+ r_i RMW_t
+ c_i CMA_t
+ ε_i,t
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| R_i,t | 銘柄またはポートフォリオのリターン |
| R_f,t | 無リスク金利 |
| R_M,t | 市場リターン |
| SMB | Small Minus Big、小型株要因 |
| HML | High Minus Low、バリュー要因 |
| RMW | Robust Minus Weak、収益性要因 |
| CMA | Conservative Minus Aggressive、投資要因 |
| α | ファクターで説明できない超過リターン |
| ε | 誤差項 |

### HMLの企業属性

```text
B/M = Book Equity / Market Equity
```

### RMWの企業属性

```text
Operating Profitability
= (Revenue - COGS - SG&A - Interest Expense) / Book Equity
```

### CMAの企業属性

```text
Investment
= (Total Assets_t - Total Assets_{t-1}) / Total Assets_{t-1}
```

### 何を意味するか

Fama-Frenchモデルは、株式リターンの横断面を以下の属性で説明する。

- 割安性
- 収益性
- 保守的な投資行動
- 企業規模
- 市場リスク

### バフェット型投資との関係

Buffett型投資の「良い会社を合理的な価格で買う」は、以下と接続する。

| Buffett型要素 | Fama-French属性 |
|---|---|
| 合理的な価格 | HML / B/M |
| 高収益 | RMW / Operating Profitability |
| 無理な拡張をしない | CMA / Conservative Investment |

### Phase1での使い方

Fama-French因子そのものを選定式にするのではなく、企業属性として使う。

- B/MはValue軸
- Operating ProfitabilityはQuality補助
- Asset GrowthはConservative Investment補助

ただし、Gross ProfitabilityやQMJと重複しやすいため、主軸は B/M と Gross Profitability に置き、RMW/CMAは理論的背景またはrobustness確認に留める。

---

## 2.5 B/M（Book-to-Market）

### 参照文献

Fama and French 1993  
Lakonishok, Shleifer, Vishny 1994  
Basu 1977/1983 などのValue研究

### 式

```text
B/M = Book Equity / Market Equity
```

または、

```text
B/M = 1 / PBR
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| Book Equity | 自己資本、簿価純資産 |
| Market Equity | 株式時価総額 |
| PBR | 株価純資産倍率 |

### 何を意味するか

株価が企業の簿価純資産に対してどの程度安いかを示す。  
高B/Mは、相対的に割安な企業を意味する。

### バフェット型投資との関係

Buffettは単なる低PBR投資家ではないが、「良い会社を高すぎない価格で買う」ため、価格規律は必要である。  
B/Mはその価格規律の一つである。

### Phase1での使い方

Value screenの一部として使う。  
ただし、低PBRだけで選ぶのではなく、Quality条件を通した企業の中で価格規律をかける。

---

## 2.6 E/P（Earnings Yield）

### 参照文献

Basu, Sanjoy.  
“Investment Performance of Common Stocks in Relation to Their Price-Earnings Ratios.” *Journal of Finance*, 1977.

Basu, Sanjoy.  
“Earnings’ Yield and the Size Effect.” *Journal of Financial Economics*, 1983.

### 式

```text
E/P = Earnings / Price
```

または実務上、

```text
E/P = Net Income / Market Capitalization
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| Earnings | 利益、通常は純利益またはEPS |
| Price | 株価 |
| Market Capitalization | 時価総額 |

### 何を意味するか

株価に対してどれだけ利益を生んでいるかを測る。  
PERの逆数である。

### バフェット型投資との関係

「利益に対して高すぎる価格で買わない」ための指標。  
Buffett型のMargin of Safetyに近い。

### Phase1での使い方

B/Mと併用する。  
赤字企業では意味が崩れるため、正のE/P企業のみを対象にする。

---

## 2.7 Piotroski F-Score

### 文献

Piotroski, Joseph D.  
“Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers.” *Journal of Accounting Research*, 2000.

### 式

```text
F-Score =
F_ROA
+ F_CFO
+ F_ΔROA
+ F_ACCRUAL
+ F_ΔMARGIN
+ F_ΔTURN
+ F_ΔLEVER
+ F_ΔLIQUID
+ EQ_OFFER
```

最大9点、最小0点。

### 9つの二値シグナル

| シグナル | 条件 | 意味 |
|---|---|---|
| F_ROA | ROA > 0 | 黒字性 |
| F_CFO | CFO > 0 | 営業CFが黒字 |
| F_ΔROA | ROA_t > ROA_{t-1} | 収益性改善 |
| F_ACCRUAL | CFO > ROA | 利益の質 |
| F_ΔMARGIN | Gross Margin_t > Gross Margin_{t-1} | 利幅改善 |
| F_ΔTURN | Asset Turnover_t > Asset Turnover_{t-1} | 資産効率改善 |
| F_ΔLEVER | Leverage_t < Leverage_{t-1} | 財務レバレッジ低下 |
| F_ΔLIQUID | Current Ratio_t > Current Ratio_{t-1} | 流動性改善 |
| EQ_OFFER | 新株発行なし | 希薄化回避 |

### 何を意味するか

F-Scoreは、割安企業の中から財務状態が良い企業を選ぶための式である。  
単に低PBRの企業を買うのではなく、低評価の中でも改善している企業を抽出する。

### バフェット型投資との関係

Buffett型投資は「安いだけの悪い会社」を避ける。  
F-Scoreは、バリュートラップを避けるための安全弁になる。

### Phase1での使い方

主ランキングではなく、Quality / Financial Strength gateとして使う。

推奨：

```text
F-Score >= 6
```

または、候補数が少なすぎる場合は `F-Score >= 5` も感度分析で確認する。

---

## 2.8 Sloan Accruals

### 文献

Sloan, Richard G.  
“Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?” *The Accounting Review*, 1996.

### 式：CFOを使う簡易形

```text
Accruals = (Net Income - Operating Cash Flow) / Average Total Assets
```

### 式：バランスシート近似

```text
Accruals =
{(ΔCurrent Assets - ΔCash)
 - (ΔCurrent Liabilities - ΔShort-term Debt - ΔTaxes Payable)
 - Depreciation} / Average Total Assets
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| Net Income | 純利益 |
| Operating Cash Flow | 営業キャッシュフロー |
| Average Total Assets | 平均総資産 |
| ΔCurrent Assets | 流動資産の増加 |
| ΔCash | 現金同等物の増加 |
| ΔCurrent Liabilities | 流動負債の増加 |
| ΔShort-term Debt | 短期借入金の増加 |
| ΔTaxes Payable | 未払税金の増加 |
| Depreciation | 減価償却費 |

### 何を意味するか

会計利益のうち、現金を伴わない発生主義部分を測る。  
Accrualsが高すぎる企業は、利益の持続性が低い可能性がある。

### バフェット型投資との関係

Buffett型投資では、会計利益ではなく実際に現金を生む力が重要。  
Sloan Accrualsは「利益が本当に現金に裏付けられているか」を確認する式である。

### Phase1での使い方

低いほど良い。  
悪い側上位30%を除外する、または最終候補のtie-breakで低Accrualsを優先する。

---

## 2.9 Ohlson O-Score

### 文献

Ohlson, James A.  
“Financial Ratios and the Probabilistic Prediction of Bankruptcy.” *Journal of Accounting Research*, 1980.

### 式

```text
O =
-1.32
- 0.407 * log(TA / GNP)
+ 6.03 * (TL / TA)
- 1.43 * (WC / TA)
+ 0.0757 * (CL / CA)
- 1.72 * OENEG
- 2.37 * (NI / TA)
- 1.83 * (FFO / TL)
+ 0.285 * INTWO
- 0.521 * CHIN
```

破綻確率への変換：

```text
P(failure) = 1 / (1 + exp(-O))
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| TA | 総資産 |
| GNP | GNP price-level index |
| TL | 総負債 |
| WC | 運転資本 |
| CL | 流動負債 |
| CA | 流動資産 |
| OENEG | 総負債が総資産を上回る場合1 |
| NI | 純利益 |
| FFO | Funds from Operations |
| INTWO | 2年連続赤字なら1 |
| CHIN | 純利益変化率 |

### 何を意味するか

財務比率を用いて企業の破綻リスクを推定する。

### バフェット型投資との関係

Buffett型投資では、永久的な資本毀損を避けることが重要。  
O-Scoreは、破綻リスクの高い企業を除外するための式として使える。

### Phase1での使い方

銘柄を選ぶためではなく、危険な企業を落とすために使う。

推奨：

```text
O-Scoreが悪い側上位10%を除外
```

ただし、GNP変数が日本株実装で取得できない場合、原式からの逸脱を明記し、rank-based distress proxyとして扱う。

---

## 2.10 Altman Z-Score

### 文献

Altman, Edward I.  
“Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy.” *Journal of Finance*, 1968.

### 式

```text
Z =
1.2 * (Working Capital / Total Assets)
+ 1.4 * (Retained Earnings / Total Assets)
+ 3.3 * (EBIT / Total Assets)
+ 0.6 * (Market Value of Equity / Total Liabilities)
+ 1.0 * (Sales / Total Assets)
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| Working Capital | 運転資本 |
| Total Assets | 総資産 |
| Retained Earnings | 利益剰余金 |
| EBIT | 利払前税引前利益 |
| Market Value of Equity | 株式時価総額 |
| Total Liabilities | 総負債 |
| Sales | 売上高 |

### 何を意味するか

企業の財務的な安全性・破綻リスクを判別する。

### バフェット型投資との関係

長期保有に耐えない企業を避けるための安全性指標。

### Phase1での使い方

O-Scoreと同様、選ぶためではなく落とすために使う。  
ただしAltman原式は公開製造業向けなので、日本株全体への絶対閾値の直用は避ける。

推奨：

```text
Altman Zが低い側下位10%を除外
```

---

## 2.11 Markowitz Portfolio Variance

### 文献

Markowitz, Harry.  
“Portfolio Selection.” *Journal of Finance*, 1952.

### 式

```text
σ_p² = Σ_i Σ_j w_i w_j σ_ij
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| σ_p² | ポートフォリオ分散 |
| w_i | 銘柄iの投資比率 |
| σ_ij | 銘柄iとjの共分散 |

### 何を意味するか

ポートフォリオ全体のリスクは、個別銘柄のリスクだけでなく、銘柄間の共分散によって決まる。

### Phase1での使い方

銘柄選定やウェイト決定には使わない。  
最終20銘柄の等金額ポートフォリオについて、分散と相関を検証するために使う。

---

## 2.12 Sharpe Ratio

### 文献

Sharpe, William F.  
“The Sharpe Ratio.” *Journal of Portfolio Management*, 1994.

### 式

```text
Sharpe Ratio = (R_p - R_f) / σ_p
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| R_p | ポートフォリオリターン |
| R_f | 無リスク金利 |
| σ_p | ポートフォリオリターンの標準偏差 |

### 何を意味するか

リスク1単位あたり、どれだけ超過リターンを得たかを測る。

### Phase1での使い方

Buffett Proxy Portfolioの検証に使う。  
TOPIXや日経平均、既存ETFとの比較に使う。

---

## 2.13 Jensen’s Alpha

### 文献

Jensen, Michael C.  
“The Performance of Mutual Funds in the Period 1945–1964.” *Journal of Finance*, 1968.

### 式

```text
R_p,t - R_f,t
= α_p
+ β_p (R_M,t - R_f,t)
+ ε_p,t
```

### 変数の意味

| 変数 | 意味 |
|---|---|
| R_p,t | ポートフォリオリターン |
| R_f,t | 無リスク金利 |
| R_M,t | 市場リターン |
| α_p | 市場要因で説明できない超過リターン |
| β_p | 市場感応度 |
| ε_p,t | 誤差項 |

### 何を意味するか

ポートフォリオの成果が市場全体の上昇だけで説明できるのか、それとも銘柄選定による超過リターンがあるのかを測る。

### Phase1での使い方

Buffett Proxy PortfolioがTOPIXや日経平均に対して独自のαを持つか検証する。

---

# 3. Codex実装プロンプト完全版

以下をCodexにそのまま貼り付けて実行させる。

---

```text
あなたは、金融経済学・会計ファイナンス・クオンツ投資・Pythonデータ分析に精通した実装担当者です。
目的は、日本株3,299社の既取得データを用いて、日経STOCKリーグ向け「BEYOND BUFFETT」Phase1（守）の
Buffett Proxy Portfolio 20銘柄を構築することです。

# 0. 最重要方針

Phase1は「守」です。
ここでは独自の重み付き合成式を作ってはいけません。

禁止例：
- MOAT = 0.35 PROF + 0.25 CF + 0.20 STAB + 0.20 COMP
- BB = 0.30 MOAT + 0.25 TRANS + 0.30 FM + 0.15 VAL
- 独自のAI関連スコア
- 独自のFuture Moatスコア
- 独自のTransformation Moatスコア
- バックテスト結果を見て銘柄を入れ替えること
- 最終20銘柄のリターン最大化を目的に条件を調整すること

Phase1で使ってよいのは、先行研究・査読論文・広く引用される実証研究で定義された式、分位ソート、二値スコア、除外条件のみです。

実装の思想は以下です。

- Buffett型投資を完全再現するのではなく、公開データで観測できる部分だけを再現する。
- 対象は Value × Quality × Profitability × Earnings Quality × Financial Strength × Low Distress。
- Future Moat、Transformation Moat、AI関連テキスト、中計テキスト、政策保有株縮減はPhase1では使わない。
- 最終ポートフォリオは20銘柄。
- ウェイトは等金額配分。
- Markowitz最適化でウェイトを決めてはいけない。Markowitzは検証のみ。
- 使えない式・欠損した式は、勝手に代替せず、「使えない」「原式から逸脱」と明記してレポートする。

# 1. 参照すべき論文・式

実装で参照する式は以下です。

## 1.1 Buffett’s Alpha
Frazzini, Kabiller, Pedersen (2018), “Buffett’s Alpha”
- Phase1の理論背景。
- Buffettの公開データ上の特徴を cheap, safe, high-quality stocks として近似する。
- 実装式として直接使うのではなく、Phase1全体の設計思想に使う。

## 1.2 Quality Minus Junk
Asness, Frazzini, Pedersen (2019), “Quality Minus Junk”
- Quality = average(Profitability, Growth, Safety, Payout)
- 各構成要素はrank-z-score化して合成。
- 必要変数が揃う場合のみ実装。
- 必要変数が不足する場合は勝手に簡略化せず、QMJ full unavailable と出力する。

## 1.3 Gross Profitability
Novy-Marx (2013)
- Gross Profitability = (Revenue - COGS) / Total Assets
- Quality / Profitability の中核に使う。

## 1.4 Fama-French / Value
Fama and French (1993, 2015), Basu (1977, 1983)
- B/M = Book Equity / Market Equity
- E/P = Earnings / Market Capitalization
- Value screenに使う。
- HML, RMW, CMAそのものは検証・説明用であり、最終選定の独自合成には使わない。

## 1.5 Piotroski F-Score
Piotroski (2000)
F-Score = 9 binary signals:
1. F_ROA: ROA > 0
2. F_CFO: CFO > 0
3. F_DROA: ROA_t > ROA_{t-1}
4. F_ACCRUAL: CFO > ROA
5. F_DMARGIN: Gross Margin_t > Gross Margin_{t-1}
6. F_DTURN: Asset Turnover_t > Asset Turnover_{t-1}
7. F_DLEVER: Leverage_t < Leverage_{t-1}
8. F_DLIQUID: Current Ratio_t > Current Ratio_{t-1}
9. EQ_OFFER: no common equity issuance

## 1.6 Sloan Accruals
Sloan (1996)
優先式:
Accruals = (Net Income - Operating Cash Flow) / Average Total Assets

CFOがない場合のみ:
Accruals =
{(ΔCurrent Assets - ΔCash)
 - (ΔCurrent Liabilities - ΔShort-term Debt - ΔTaxes Payable)
 - Depreciation} / Average Total Assets

低いほど良い。
高Accrual銘柄は利益の質が低い可能性がある。

## 1.7 Ohlson O-Score
Ohlson (1980)
O =
-1.32
- 0.407 * log(TA / GNP)
+ 6.03 * (TL / TA)
- 1.43 * (WC / TA)
+ 0.0757 * (CL / CA)
- 1.72 * OENEG
- 2.37 * (NI / TA)
- 1.83 * (FFO / TL)
+ 0.285 * INTWO
- 0.521 * CHIN

P(failure) = 1 / (1 + exp(-O))

注意:
- GNPが取得できない場合、勝手にlog(TA)へ置き換える前に必ず実装レポートで「原式からの逸脱」と明記する。
- 必要変数が欠ける場合、O-Scoreは計算不能として扱う。
- O-Scoreは選定ではなく除外条件に使う。

## 1.8 Altman Z-Score
Altman (1968)
Z =
1.2 * (Working Capital / Total Assets)
+ 1.4 * (Retained Earnings / Total Assets)
+ 3.3 * (EBIT / Total Assets)
+ 0.6 * (Market Value of Equity / Total Liabilities)
+ 1.0 * (Sales / Total Assets)

注意:
- 原式は公開製造業向け。
- 日本株全体に絶対閾値を直用しない。
- cross-sectional rank / bottom-tail exclusionとして使う。

## 1.9 Markowitz
Markowitz (1952)
Portfolio Variance = Σ_i Σ_j w_i w_j cov_ij
- 選定式ではない。
- 最終20銘柄のリスク検証に使う。

## 1.10 Sharpe Ratio
Sharpe (1994)
Sharpe = (R_p - R_f) / sigma_p
- 検証に使う。

## 1.11 Jensen’s Alpha
Jensen (1968)
R_p,t - R_f,t = alpha + beta * (R_m,t - R_f,t) + error
- TOPIXまたは日経平均に対するCAPM alphaを検証する。

# 2. 入力データの前提

ローカル環境に日本株3,299社のデータがある前提で実装する。
データファイル名は実際のリポジトリを探索して確認すること。

想定される入力：
- universe.csv
- prices.csv
- financials.csv
- sectors.csv
- market_cap.csv
- jpx_listed_companies.csv
- edinet_financials.csv
- returns.csv

ただし、ファイル名を決め打ちせず、まずリポジトリ内を探索して、利用可能なデータを data_inventory.md にまとめること。

# 3. データ処理ルール

## 3.1 ユニバース

対象：
- 普通株
- 日本株
- 分析可能な企業

除外：
- ETF
- REIT
- 優先株
- 外国株扱い
- 金融業
- 保険業
- 銀行業
- 証券・商品先物
- その他金融業
- 必要データが大きく欠損している企業
- 価格系列が取得できない企業
- 極端に流動性が低い企業

金融除外はJPX33業種または利用可能な業種分類で行う。
分類名が日本語の場合は以下を除外：
- 銀行業
- 保険業
- 証券、商品先物取引業
- その他金融業

英語の場合は以下を除外：
- Banks
- Insurance
- Securities and Commodities Futures
- Other Financing Business

## 3.2 Look-ahead bias回避

会計データは、その会計年度末時点で即座に使えるものとして扱ってはいけない。

優先順位：
1. disclosure_date / filing_date がある場合、その日以降にのみ利用
2. なければ fiscal_year_end + 120日 を利用可能日とする
3. それも不可能なら、look-ahead riskとして明記する

すべての出力に、どの時点基準で計算したかを記録する。

## 3.3 欠損処理

- 欠損を勝手に平均代入しない
- 重要変数がない式は計算不能とする
- 計算不能件数を式ごとに出す
- QMJ full が計算不能なら、その理由を明記する
- O-Score が計算不能なら、その理由を明記する
- 欠損理由を missingness_report.csv に出力する

## 3.4 外れ値処理

- winsorize は使ってよい
- ただし上下何%で処理したか明記する
- 推奨は上下1%または上下2.5%
- 処理前後の分布を出力する
- winsorize_log.csv に記録する

# 4. 実装手順

## Step 0: Repository audit

まず、現在のリポジトリを調査し、以下を出力する。

成果物：
- submission_assets/phase1/data_inventory.md
- submission_assets/phase1/input_file_map.csv

data_inventory.mdには以下を書く：
- 利用可能なデータファイル
- 各ファイルの列名
- 企業コード列
- 年度列
- 日付列
- 財務データの粒度
- 価格データの粒度
- 欠損が多そうな列
- 実装に必要だが不足している列

## Step 1: Universe construction

非金融の普通株ユニバースを作成する。

成果物：
- submission_assets/phase1/phase1_universe.csv
- submission_assets/phase1/universe_exclusion_reasons.csv
- submission_assets/phase1/universe_summary.csv

phase1_universe.csvの必須列：
- code
- ticker
- company_name
- sector
- market_segment
- is_financial
- is_common_stock
- data_available
- included_phase1
- exclusion_reason

universe_summary.csvの必須行：
- raw_universe_count
- common_stock_count
- after_financial_exclusion_count
- after_data_availability_count
- final_phase1_universe_count

## Step 2: Calculate Value metrics

計算する：
- Book Equity
- Market Equity
- B/M
- PBR
- E/P
- PER
- positive_earnings_flag

成果物：
- submission_assets/phase1/value_metrics.csv
- submission_assets/phase1/value_metric_summary.csv

注意：
- Book Equity <= 0 の企業はB/M計算不可
- Earnings <= 0 の企業はE/P計算不可
- 異常値はwinsorizeし、ログに残す

## Step 3: Calculate Profitability / Quality metrics

計算する：
- Gross Profit
- Gross Profitability = Gross Profit / Total Assets
- ROA
- ROE
- CFO / Assets
- Gross Margin
- Asset Turnover
- Operating Profitability
- Asset Growth

可能ならQMJ fullを実装する。
QMJ fullに必要な変数が不足する場合、勝手な独自QMJを作らず、
「QMJ full unavailable」として qmj_availability_report.md に書く。

成果物：
- submission_assets/phase1/quality_metrics.csv
- submission_assets/phase1/qmj_metrics.csv
- submission_assets/phase1/qmj_availability_report.md
- submission_assets/phase1/quality_metric_summary.csv

## Step 4: Calculate Piotroski F-Score

9シグナルを計算する。

成果物：
- submission_assets/phase1/piotroski_fscore.csv
- submission_assets/phase1/piotroski_signal_summary.csv

piotroski_fscore.csvの必須列：
- code
- ticker
- company_name
- F_ROA
- F_CFO
- F_DROA
- F_ACCRUAL
- F_DMARGIN
- F_DTURN
- F_DLEVER
- F_DLIQUID
- EQ_OFFER
- F_SCORE
- missing_signal_count
- fscore_reliability_flag

## Step 5: Calculate Sloan Accruals

優先的にCFOベースで計算。
CFOがない場合のみバランスシート近似を使う。

成果物：
- submission_assets/phase1/accruals_metrics.csv
- submission_assets/phase1/accruals_method_report.md

必須列：
- code
- accruals
- accruals_method
- net_income
- operating_cash_flow
- average_total_assets
- accruals_rank
- high_accrual_flag

## Step 6: Calculate Distress metrics

Ohlson O-ScoreとAltman Z-Scoreを計算する。

成果物：
- submission_assets/phase1/distress_metrics.csv
- submission_assets/phase1/ohlson_implementation_report.md
- submission_assets/phase1/altman_implementation_report.md

注意：
- O-ScoreでGNPが取れない場合は明記
- O-Scoreが原式通りでない場合は、原式からの逸脱として明記
- Altman Zは原式が公開製造業向けであることを明記
- 絶対閾値ではなくcross-sectional rankで除外する

## Step 7: Apply sequential academic screens

以下の順にスクリーニングする。

### 7.1 Value screen

条件：
- B/M 上位30%を通過
- positive E/P銘柄のうち E/P 上位50%を通過
- 上記両方を満たす銘柄を残す

### 7.2 Quality / Profitability screen

条件：
- Gross Profitability がユニバース中央値以上
- QMJ fullが計算可能なら QMJ overall quality が中央値以上
- QMJ fullが計算不能なら、Gross ProfitabilityとF-Scoreを主品質proxyとして扱う

### 7.3 Financial strength screen

条件：
- F-Score >= 6

### 7.4 Earnings quality screen

条件：
- Sloan Accruals の悪い側上位30%を除外

### 7.5 Distress exclusion

条件：
- O-Scoreが計算可能なら、悪い側上位10%を除外
- Altman Zが計算可能なら、低い側下位10%を除外
- 両方ある場合、どちらかで極端に悪い銘柄を除外

成果物：
- submission_assets/phase1/screening_steps.csv
- submission_assets/phase1/phase1_candidates.csv
- submission_assets/phase1/screening_funnel.csv
- submission_assets/phase1/screening_funnel_report.md

screening_steps.csvの必須列：
- step
- criterion
- count_before
- count_after
- removed_count
- explanation
- source_paper

phase1_candidates.csvの必須列：
- code
- ticker
- company_name
- sector
- market_segment
- B_M
- E_P
- gross_profitability
- qmj_quality
- f_score
- accruals
- o_score
- altman_z
- value_bucket
- quality_bucket
- included_candidate
- notes

## Step 8: Final selection by Quality × Value double sort

残存銘柄に対し、二重ソートを行う。

Value：
- B/M tercile
- E/P tercile
- high value の定義を明記

Quality：
- QMJ fullがあれば QMJ quality tercile
- QMJ fullがなければ Gross Profitability tercile
- F-Scoreを補助条件にする

最終候補：
- High Value × High Quality セル

候補が20超の場合、以下の順でtie-breakする。
1. higher F-Score
2. lower Sloan Accruals
3. higher Gross Profitability
4. lower O-Score
5. higher Altman Z
6. larger Market Capitalization

候補が20未満の場合：
- 条件を勝手に変更しない。
- どの条件で不足したかを報告し、代替案として以下を出す。
  A. F-Score >= 5 に緩和した場合
  B. E/P上位60%に緩和した場合
  C. Gross Profitability中央値以上を維持しつつValue条件を緩和した場合
- ただし採用案は必ずレポートで理由を書く。

成果物：
- submission_assets/phase1/phase1_double_sort.csv
- submission_assets/phase1/phase1_final20.csv
- submission_assets/phase1/final20_selection_reason.md

phase1_final20.csvの必須列：
- rank
- code
- ticker
- company_name
- sector
- market_segment
- market_cap
- B_M
- E_P
- gross_profitability
- qmj_quality
- f_score
- accruals
- o_score
- altman_z
- value_bucket
- quality_bucket
- final_weight
- investment_amount_yen
- selection_reason
- caution

final_weightは全銘柄5%。
500万円ポートフォリオなら投資額は各250,000円を基本とする。
株数計算が必要な場合は、直近日終値で floor(investment_amount / close_price) とする。

## Step 9: Validation

最終20銘柄について、可能な範囲で以下を検証する。

- 累積リターン
- 年率リターン
- 年率ボラティリティ
- Sharpe Ratio
- Max Drawdown
- TOPIXまたは1306.Tとの比較
- 日経平均との比較
- Jensen's Alpha
- beta
- Markowitz portfolio variance
- 相関ヒートマップ
- セクター配分
- 指標分布

成果物：
- submission_assets/phase1/backtest_summary.csv
- submission_assets/phase1/jensen_alpha.csv
- submission_assets/phase1/portfolio_variance.csv
- submission_assets/phase1/sector_allocation.csv
- submission_assets/phase1/final20_metric_distribution.csv
- submission_assets/phase1/charts/phase1_screening_funnel.png
- submission_assets/phase1/charts/phase1_sector_allocation.png
- submission_assets/phase1/charts/phase1_backtest_vs_benchmark.png
- submission_assets/phase1/charts/phase1_correlation_heatmap.png

注意：
- Validation結果で銘柄を入れ替えない。
- Backtestは検証であり、選定条件の最適化に使わない。
- look-ahead bias, survivorship bias, data availability biasをlimitationsに書く。

## Step 10: Report-ready outputs

以下のMarkdownを生成する。

### 10.1 phase1_methodology.md

内容：
- Phase1の目的
- なぜ独自式を避けるのか
- Buffett Proxyの定義
- 採用した論文式
- 採用しなかった式
- 金融業を除外した理由
- データ制約
- look-ahead回避方法
- スクリーニング手順

### 10.2 phase1_formula_reference.md

内容：
- 各式の出典
- 式
- 変数定義
- 何を測るか
- Buffett型投資との対応
- 日本株実装上の注意
- 今回の実装状況

### 10.3 phase1_final20_report.md

内容：
- 最終20銘柄一覧
- 各銘柄の選定理由
- Value, Quality, F-Score, Accruals, Distressの観点
- セクター分布
- Phase1ポートフォリオとしての解釈
- 限界

### 10.4 phase1_limitations.md

内容：
- Buffettを完全再現できない理由
- 保険フロートを再現できない
- 非公開企業買収を再現できない
- 経営者評価を再現できない
- EDINET・価格データの制約
- 金融業除外の限界
- survivorship bias
- look-ahead bias
- backtestは将来を保証しない

### 10.5 README_phase1_reproducibility.md

内容：
- 実行手順
- 必要ライブラリ
- 入力データ
- 出力データ
- 再現方法
- 監査ポイント

# 5. 最終出力ディレクトリ構成

必ず以下の構成で出力する。

submission_assets/
  phase1/
    data_inventory.md
    input_file_map.csv
    phase1_universe.csv
    universe_exclusion_reasons.csv
    universe_summary.csv
    value_metrics.csv
    quality_metrics.csv
    qmj_metrics.csv
    qmj_availability_report.md
    piotroski_fscore.csv
    accruals_metrics.csv
    distress_metrics.csv
    screening_steps.csv
    screening_funnel.csv
    phase1_candidates.csv
    phase1_double_sort.csv
    phase1_final20.csv
    final20_selection_reason.md
    backtest_summary.csv
    jensen_alpha.csv
    portfolio_variance.csv
    sector_allocation.csv
    final20_metric_distribution.csv
    phase1_methodology.md
    phase1_formula_reference.md
    phase1_final20_report.md
    phase1_limitations.md
    README_phase1_reproducibility.md
    charts/
      phase1_screening_funnel.png
      phase1_sector_allocation.png
      phase1_backtest_vs_benchmark.png
      phase1_correlation_heatmap.png
  scripts/
    phase1_build_universe.py
    phase1_compute_metrics.py
    phase1_screening.py
    phase1_select_final20.py
    phase1_validate_portfolio.py
    phase1_generate_report_assets.py

# 6. 品質チェック

実装後、以下を確認する。

- 独自重み付きスコアを作っていないか
- Future MoatやAI関連語を使っていないか
- Transformation要素を使っていないか
- 金融業が除外されているか
- 各式の計算不能件数を出しているか
- QMJ fullができない場合に勝手な簡略版を作っていないか
- O-Scoreの原式逸脱を明記しているか
- Altman Zを絶対閾値で乱用していないか
- 最終20銘柄がbacktest結果で入れ替えられていないか
- 最終20銘柄が等金額配分になっているか
- すべての出力CSVにcode, ticker, company_nameがあるか
- Markdownレポートがそのまま本文に使える水準か

# 7. 最終メッセージ

完了時には、以下を報告する。

1. Phase1ユニバースの社数
2. 各スクリーニング通過数
3. 最終20銘柄
4. 使えた式・使えなかった式
5. QMJ fullの可否
6. O-Scoreの可否
7. 主な欠損・制約
8. 検証結果の概要
9. 出力ファイル一覧
10. 次に人間が確認すべきポイント
```

---

# 4. Codex実行後に人間が確認すべきポイント

Codexに実装させた後、そのまま採用せず、人間側で以下を確認する。

## 4.1 研究設計の確認

- 本当に独自合成式を使っていないか
- Phase1にFuture MoatやTransformation要素が混ざっていないか
- 先行研究式の出典が明記されているか
- 原式から逸脱した部分が明記されているか

## 4.2 データ品質の確認

- EDINET由来の財務指標が正しく使われているか
- 価格データと会計データの時点がズレていないか
- look-ahead biasが発生していないか
- 欠損が多い式を無理に使っていないか

## 4.3 最終20銘柄の確認

- 低PBRだけの企業になっていないか
- 高Qualityだけで高値掴みになっていないか
- 市況株や一時的利益企業に偏っていないか
- セクターが偏りすぎていないか
- Buffett Proxyとして説明可能か

## 4.4 レポート本文への接続

- Phase1の結果が「守」として機能しているか
- Phase2の「破」で間口を広げる必要性が説明できるか
- Phase3の「離」でFuture Moat/Transformation Moatに進む理由が作れるか

---

# 5. レポート用まとめ文

## 5.1 Phase1の説明文

本研究のPhase1では、独自の重み付き合成式を用いず、先行研究で定義された式・分位ソート・除外条件だけを用いて、バフェット型投資を公開データで再現する。これは、Phase1が守・破・離の「守」にあたるためである。ここで独自式を用いると、係数の恣意性が入り、後続フェーズで何を拡張したのかが不明確になる。そこで本研究では、Buffett’s Alpha、Quality Minus Junk、Gross Profitability、Fama-French/Basu系のValue指標、Piotroski F-Score、Sloan Accruals、Ohlson O-Score、Altman Z-Scoreを用いて、公開データから観測可能な「割安・高品質・安全な企業」を抽出する。

## 5.2 Buffett Proxyの説明文

本研究が構築するPhase1ポートフォリオは、Buffett本人の投資判断を完全に再現するものではない。Buffettの投資には、保険フロート、非公開企業買収、経営者評価、交渉力、長期的関係資本など、公開データでは観測できない要素が含まれるためである。したがって本研究では、公開財務データで観測できるValue、Quality、Profitability、Earnings Quality、Financial Strength、Low Distressに限定し、Buffett Proxy Portfolioとして20銘柄を構成する。

## 5.3 Phase2への接続文

Phase1では、先行研究式に基づいて完成された堀を持つ企業を抽出する。しかし、この方法は既に財務諸表に強さが表れている企業に偏りやすく、これから変化する企業や、将来の産業構造変化によって新たな堀を形成しうる企業を早期に除外する可能性がある。そこでPhase2では、Phase1で用いた式そのものは変えず、その適用閾値・分位・通過条件をAIで最適化し、守る堀の最低条件を保ったまま、後続分析に進める候補企業群の間口を広げる。

---

# 6. 参考文献一覧

- Asness, C. S., Frazzini, A., & Pedersen, L. H. (2019). “Quality Minus Junk.” *Review of Accounting Studies*.
- Altman, E. I. (1968). “Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy.” *Journal of Finance*.
- Basu, S. (1977). “Investment Performance of Common Stocks in Relation to Their Price-Earnings Ratios.” *Journal of Finance*.
- Basu, S. (1983). “Earnings’ Yield and the Size Effect.” *Journal of Financial Economics*.
- Fama, E. F., & French, K. R. (1993). “Common Risk Factors in the Returns on Stocks and Bonds.” *Journal of Financial Economics*.
- Fama, E. F., & French, K. R. (2015). “A Five-Factor Asset Pricing Model.” *Journal of Financial Economics*.
- Frazzini, A., Kabiller, D., & Pedersen, L. H. (2018). “Buffett’s Alpha.” *Financial Analysts Journal*.
- Jensen, M. C. (1968). “The Performance of Mutual Funds in the Period 1945–1964.” *Journal of Finance*.
- Lakonishok, J., Shleifer, A., & Vishny, R. W. (1994). “Contrarian Investment, Extrapolation, and Risk.” *Journal of Finance*.
- Markowitz, H. (1952). “Portfolio Selection.” *Journal of Finance*.
- Novy-Marx, R. (2013). “The Other Side of Value: The Gross Profitability Premium.” *Journal of Financial Economics*.
- Ohlson, J. A. (1980). “Financial Ratios and the Probabilistic Prediction of Bankruptcy.” *Journal of Accounting Research*.
- Piotroski, J. D. (2000). “Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers.” *Journal of Accounting Research*.
- Sharpe, W. F. (1994). “The Sharpe Ratio.” *Journal of Portfolio Management*.
- Sloan, R. G. (1996). “Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?” *The Accounting Review*.

