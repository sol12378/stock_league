# Phase1 式の説明（formula explanation）

様式は `phase0_input_audit/outliers_style_extraction.md` の4段構成（導入→式→変数定義→直感）に従う。定義は $\coloneqq$、会計項目はローマン体。

## 1. B/M（Book-to-Market）

株主資本の簿価に対して市場評価がどれだけ低いかを測る。Fama and French (1993) の Value ファクターの基礎である。

$$
\mathrm{BM}_i \coloneqq \frac{\mathrm{BE}_i}{\mathrm{ME}_i}
\tag{1}
$$

ここで，$\mathrm{BE}_i$ は企業 $i$ の簿価自己資本，$\mathrm{ME}_i$ は時価総額（株価×発行済株式数）である。$\mathrm{BM}_i = 1/\mathrm{PBR}_i$ の関係にある。

> **直感**：簿価自己資本 100 億円の会社を市場が 80 億円で評価していれば $\mathrm{BM} = 100/80 = 1.25$。1 を超えるほど「簿価より安く買える」。ただし高 B/M は衰退企業の兆候でもあるため、Quality 指標と必ず併用する（バリュートラップ対策）。

## 2. E/P（Earnings Yield）

株価に対する利益の水準を測る。Basu (1977, 1983) が low P/E 効果として示した指標の逆数形である。

$$
\mathrm{EP}_i \coloneqq \frac{\mathrm{E}_i}{\mathrm{ME}_i}, \qquad \mathrm{E}_i > 0
\tag{2}
$$

ここで，$\mathrm{E}_i$ は直近会計年度の純利益である。負の利益は比率の解釈が壊れるため，**正の利益のみ**を採用する。

> **直感**：E/P 0.20 は「投資額の 20% に相当する利益を毎年生む価格で買える」ことを意味する（PER 5 倍）。

## 3. Gross Profitability

総資産に対する売上総利益の水準で「収益力の質」を測る。Novy-Marx (2013) は，粗利益ベースの収益性が純利益よりも将来収益性の持続を予測することを示した。

$$
\mathrm{GPA}_i \coloneqq \frac{\mathrm{GP}_i}{\mathrm{TA}_i} = \frac{\mathrm{REV}_i - \mathrm{COGS}_i}{\mathrm{TA}_i}
\tag{3}
$$

ここで，$\mathrm{GP}_i$ は売上総利益，$\mathrm{REV}_i$ は売上高，$\mathrm{COGS}_i$ は売上原価，$\mathrm{TA}_i$ は総資産である。

> **注意**：資産回転の速い小売業で構造的に高く出やすい。Phase1 では「同一業種原則2社まで」の上限でこのバイアスを緩和した。

## 4. Piotroski available ratio

財務健全性のシグナル数を測る。Piotroski (2000) の F-Score（9 シグナル）のうち，取得可能な 6 シグナルによる部分実装である。

$$
R^{\mathrm{avail}}_i \coloneqq \frac{\sum_{s \in \mathcal{S}^{\mathrm{avail}}_i} F_{i,s}}{\left| \mathcal{S}^{\mathrm{avail}}_i \right|}, \qquad F_{i,s} \in \{0,1\}
\tag{4}
$$

ここで，$\mathcal{S}^{\mathrm{avail}}_i$ は企業 $i$ について算出可能なシグナル集合（最大 6），$F_{i,s}$ は各シグナルの合格（1）／不合格（0）である。通過条件は $R^{\mathrm{avail}}_i \ge 0.65$（6 シグナル中 4 以上に相当）。

> **正直な開示**：これは完全な F-Score ではない。「available ratio」という名称で部分実装であることを明示し，欠損を透明に扱う。

## 5. Sloan Accruals

利益と現金の乖離（アクルーアル）で利益の質を測る。Sloan (1996) は高アクルーアル企業の利益が持続しにくいことを示した。

$$
\mathrm{Accruals}_i \coloneqq \frac{\mathrm{NI}_i - \mathrm{CFO}_i}{\overline{\mathrm{TA}}_{i,t}}, \qquad
\overline{\mathrm{TA}}_{i,t} \coloneqq \frac{\mathrm{TA}_{i,t} + \mathrm{TA}_{i,t-1}}{2}
\tag{5}
$$

ここで，$\mathrm{NI}_i$ は純利益，$\mathrm{CFO}_i$ は営業キャッシュフロー，$\overline{\mathrm{TA}}_{i,t}$ は平均総資産である。悪い側（高アクルーアル）上位 30% を除外する。

> **直感**：利益は出ているのに現金が入っていない企業は，利益の質が低い可能性が高い。

## 6. 流動性フィルタ

仮想ポートフォリオ（500 万円）の執行可能性を担保する実務ガードレールである。

$$
\mathrm{ADV}_{i,60} \coloneqq \frac{1}{60} \sum_{d=1}^{60} P_{i,d} \, V_{i,d}
\tag{6}
$$

ここで，$P_{i,d}$ は日次終値，$V_{i,d}$ は日次出来高である。$\mathrm{ADV}_{i,60} < 300$ 万円で除外，$\ge 1{,}000$ 万円で pass，中間は review とする。

## 7. Distress guardrail（Ohlson/Altman の代替）

Ohlson (1980) O-Score・Altman (1968) Z-Score は入力変数欠損により原式未実装。代替として次の複合フラグを用いる：債務超過，2 期連続損失，営業キャッシュフロー赤字，営業赤字，高負債・低自己資本比率。いずれかに該当すれば除外または review。

> **注意**：これは公刊式ではなく実装ガードレールである。「先行研究式による抽出」の例外はこの項目のみであり，未実装の理由（変数欠損）と代替設計を開示している。
