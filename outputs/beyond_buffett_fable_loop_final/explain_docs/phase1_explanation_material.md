# Phase1「守」説明資料（explanation material）

## まず結果

Phase1 は、先行研究の式**だけ**を使い、東証上場企業から「すでに完成された Moat（持続的競争優位）」を持つ 5 社を抽出した。

**ファネル**: 3,099（指標算出可能な非金融普通株）→ 2,740（Value）→ 583（Quality）→ 146（財務健全性）→ 112（利益の質）→ 90（Distress 除外後）→ 77（流動性 pass）→ **Top5**

**Buffett Core Top5（最終20社に固定組込・目標配分20〜25%）**

| rank | code | 社名 | sector | 特徴 |
|---|---|---|---|---|
| 1 | 3539 | JM HOLDINGS | Retail Trade | B/M 76%ile・E/P 95%ile・GP 92%ile、Piotroski 6/6 |
| 2 | 4350 | メディカルシステムネットワーク | Retail Trade | B/M 77%ile・E/P 92%ile・GP 91%ile、Piotroski 6/6 |
| 3 | 6430 | 大黒電機 | Machinery | E/P 97%ile が突出、Piotroski 4/6 |
| 4 | 7803 | ブシロード | Other Products | Value・Quality バランス型、Piotroski 6/6 |
| 5 | 9470 | 学研HD | 情報・通信 | B/M 80%ile、Piotroski 6/6 |

## なぜ Phase1 が必要か（守・破・離の「守」）

バフェット型投資の本質は「割安さ」ではなく「Moat を持つ企業を適正価格以下で買う」ことにある。Phase1 はこの本質を、検証可能な公刊研究の式に翻訳する段階である。ここで独自の工夫を一切しないこと（＝守）が、Phase2「破」・Phase3「離」の独自性を測る**基準線**になる。

## 使用指標と先行研究の対応

| 役割 | 指標 | 先行研究 | 通過条件 |
|---|---|---|---|
| Value | B/M | Fama and French (1993) | 上位30% |
| Value | E/P | Basu (1977, 1983) | 正の利益かつ上位50% |
| Quality | Gross Profitability | Novy-Marx (2013) | 中央値以上 |
| 財務健全性 | Piotroski available ratio | Piotroski (2000) | ≥ 0.65（6実装シグナル中4以上） |
| 利益の質 | Sloan Accruals | Sloan (1996) | 悪い側上位30%を除外 |
| 破綻回避 | simple distress guardrail | Ohlson (1980)・Altman (1968) の代替 | 該当フラグなし |
| 執行可能性 | 60日平均売買代金 | 実務ガードレール | ≥1,000万円で pass |

> **正直な開示**：Piotroski は 9 シグナル中 6 のみデータ取得可能なため「available ratio」方式（分母=取得可能シグナル数）を採用。Ohlson O-Score / Altman Z-Score は入力変数（GNP物価指数・運転資本・利益剰余金等）が取得不能で**原式未実装**。無理なプロキシ実装は「先行研究式の忠実な適用」という Phase1 の性格を損なうため、負債・損失・キャッシュフローに基づく simple distress guardrail で代替し、その旨を明記する。

## Top5 の決め方（重み付き合成スコアを使わない）

全条件通過後の 77 社から、**独自の重み付きスコアを作らず**、GP → E/P → B/M → Piotroski ratio → Sloan → 流動性 → 時価総額 の**固定順序の逐次 tie-break** で上位化した。恣意的な重み設定の余地を排除するためである。

### 同一業種は原則2社まで（重要）

GP（売上総利益/総資産）は資産回転の速い**小売業で構造的に高く出やすい**。この業種バイアスを無制限に許すと Top5 が小売で埋まるため、「同一業種原則2社まで」の上限を課した。この結果、sector-adjusted final20 の rank 3・4 に入っていた小売2社（9990、8278）は Top5 から外れ、rank 5〜7 の 6430・7803・9470 が繰り上がった。**Top5 と final20 の rank が非連続なのはこの業種上限によるもの**であり、恣意的な差し替えではない。

## 限界（レポート転用時に必ず記載）

1. Piotroski は 6/9 シグナルの available 版であり、原式 F-Score より情報量が少ない。
2. Ohlson/Altman 原式は未実装（上記開示のとおり）。
3. GP は業種によって出やすさが異なる（業種上限で部分的に緩和）。
4. 現時点データでの検証には look-ahead bias の懸念が残る（Phase2 で point-in-time panel により部分対処）。
5. 配当データに取得元による乖離あり（6430: 会社予想ベース 4.25% vs 実績トレーリング 0%）。
6. 先行研究式は将来リターンを保証しない。Phase1 の目的は「完成された Moat の抽出」であり、リターン予測ではない。
