# Phase1 Top5 Report Section

Phase1は、当初の20社すべてを説明する役割から、最終20社に組み込む守の中核銘柄を抽出する役割へ圧縮した。30ページ以内のレポートで20社すべての定量選定理由を厚く書くと、破・離フェーズで扱う変わるMoat・生まれるMoatの説明余地が不足するためである。

Phase1 Top5は、Value、Quality、Financial Strength、Earnings Quality、Low Distress、Liquidityを満たす `Buffett Core` と位置づける。ValueはB/MとE/P、QualityはGross Profitability、Financial StrengthはPiotroski available signal score、Earnings QualityはSloan Accrualsで確認した。Ohlson O-ScoreとAltman Z-Scoreは必要変数を再探索したが、原式忠実実装には不足があったため、Top5選定の主条件には使わず、simple distress guardrailでLow Distressを確認した。

選定フローは、非金融普通株から各指標が利用可能な銘柄を抽出し、B/M上位30%、positive E/P上位50%、Gross Profitability中央値以上、Piotroski available ratio 0.65以上、Sloan Accrualsの悪い側上位30%除外、distress review/exclusionなし、流動性pass、主要異常値なしの順に絞り込む。その後、重み付き総合スコアは作らず、Gross Profitability、E/P、B/M、Piotroski ratio、Sloan Accruals、Liquidity、Market capの逐次tie-breakでTop5を決めた。

## Top5一覧

| rank | code | company_name | sector | bm_raw | ep_raw | gross_profitability | piotroski_available_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3539 | JM HOLDINGS CO.,LTD. | Retail Trade | 1.4261 | 0.2041 | 0.7349 | 1.0000 |
| 2 | 4350 | MEDICAL SYSTEM NETWORK Co.,Ltd. | Retail Trade | 1.4402 | 0.1743 | 0.7188 | 1.0000 |
| 3 | 6430 | DAIKOKU DENKI CO.,LTD. | Machinery | 1.4680 | 0.2505 | 0.4661 | 0.6667 |
| 4 | 7803 | Bushiroad Inc. | Other Products | 1.4416 | 0.2051 | 0.4014 | 1.0000 |
| 5 | 9470 | GAKKEN HOLDINGS CO.,LTD. | Information & Communication | 1.5260 | 0.1215 | 0.3948 | 1.0000 |

このTop5は最終20社全体ではなく、最終20社の中に必ず組み込む守る堀Core枠である。残り15社は破・離フェーズで選びつつ、最低限の守る堀ガードレールを通す。Phase1の限界は、Buffett本人の経営者評価、保険フロート、非公開企業買収を再現しない点、Piotroskiがavailable版である点、Ohlson/Altman原式が未実装である点にある。したがってPhase1は、将来のMoatを語る前に、割安・高品質・安全性という土台を置く段階として使う。

## 各社の採用理由

# Top5 Company Rationale

## 3539 JM HOLDINGS CO.,LTD.

JM HOLDINGS CO.,LTD.（Retail Trade）は、B/M 1.426、E/P 0.204 でValue条件を満たし、合理的価格で買える候補である。Gross Profitabilityは 0.735、分位 91.8% でQualityも高い。Piotroski available signal scoreは 6/6、Sloan Accrualsは -0.002。Ohlson/Altman原式は使わず、simple distress guardrailで除外・reviewフラグなしを確認した。60日平均売買代金は 144,716,800 円で流動性もpass。主要な異常値フラグなし。残るリスクは、業種固有の景気感応度やGross Profitabilityの会計構造差である。

## 4350 MEDICAL SYSTEM NETWORK Co.,Ltd.

MEDICAL SYSTEM NETWORK Co.,Ltd.（Retail Trade）は、B/M 1.440、E/P 0.174 でValue条件を満たし、合理的価格で買える候補である。Gross Profitabilityは 0.719、分位 91.2% でQualityも高い。Piotroski available signal scoreは 6/6、Sloan Accrualsは -0.026。Ohlson/Altman原式は使わず、simple distress guardrailで除外・reviewフラグなしを確認した。60日平均売買代金は 30,067,965 円で流動性もpass。主要な異常値フラグなし。残るリスクは、業種固有の景気感応度やGross Profitabilityの会計構造差である。

## 6430 DAIKOKU DENKI CO.,LTD.

DAIKOKU DENKI CO.,LTD.（Machinery）は、B/M 1.468、E/P 0.250 でValue条件を満たし、合理的価格で買える候補である。Gross Profitabilityは 0.466、分位 78.5% でQualityも高い。Piotroski available signal scoreは 4/6、Sloan Accrualsは 0.001。Ohlson/Altman原式は使わず、simple distress guardrailで除外・reviewフラグなしを確認した。60日平均売買代金は 161,995,897 円で流動性もpass。主要な異常値フラグなし。残るリスクは、業種固有の景気感応度やGross Profitabilityの会計構造差である。

## 7803 Bushiroad Inc.

Bushiroad Inc.（Other Products）は、B/M 1.442、E/P 0.205 でValue条件を満たし、合理的価格で買える候補である。Gross Profitabilityは 0.401、分位 72.2% でQualityも高い。Piotroski available signal scoreは 6/6、Sloan Accrualsは -0.044。Ohlson/Altman原式は使わず、simple distress guardrailで除外・reviewフラグなしを確認した。60日平均売買代金は 159,848,943 円で流動性もpass。主要な異常値フラグなし。残るリスクは、業種固有の景気感応度やGross Profitabilityの会計構造差である。

## 9470 GAKKEN HOLDINGS CO.,LTD.

GAKKEN HOLDINGS CO.,LTD.（Information & Communication）は、B/M 1.526、E/P 0.122 でValue条件を満たし、合理的価格で買える候補である。Gross Profitabilityは 0.395、分位 71.3% でQualityも高い。Piotroski available signal scoreは 6/6、Sloan Accrualsは -0.023。Ohlson/Altman原式は使わず、simple distress guardrailで除外・reviewフラグなしを確認した。60日平均売買代金は 121,937,937 円で流動性もpass。主要な異常値フラグなし。残るリスクは、業種固有の景気感応度やGross Profitabilityの会計構造差である。
