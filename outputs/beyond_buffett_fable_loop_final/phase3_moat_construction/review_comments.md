# Phase3 Review Comments（loop 1）

## 良い点

1. **「離」が小手先でない**：Transformation / Emerging の両スコアとも部品が Phase1/2 の先行研究式（B/M・E/P・Piotroski・Sloan・GP・guardrail）の再構成であることが数値検証（再構築誤差 0.0）つきで示せる。「低PBR単独」は low_pbr_only_flag（value≥70 かつ TQ=0）で、「AIキーワード単独」は hype penalty（−18）と ai_keyword_only ガードで、それぞれ構造的に排除。
2. **Evidence の抑制的な扱い**：Evidence ボーナスは最大 +8 に抑えられ、証拠が「加点の主役」にならない。キーワードのみ（L1）は強い開示として扱わない。
3. **役割設計の必然性**：Buffett Core（完成した Moat）× Transformation（変わる Moat）× Emerging（生まれる Moat）× Dual × Bridge という時間軸の異なる Moat の組み合わせが、テーマ集中（non_ai 10 社・テーマ上限4）と業種集中（上限3）の両方を機械的に抑えている。
4. **監査可能性**：rejected 862 行・selection audit trail・v1 保存・MANIFEST の SHA-256 が揃い、選定の再現・反証が可能。

## 懸念点（開示・定量化で対応）

1. **curated evidence 依存**（D2）：EM≥2 の 14 社は全て手作業 URL 由来。裏を返せば「開示を読んだ企業しか L2+ になれない」ため、未読企業の過小評価リスクがある。→ リスク分析に「開示資料不足による過小評価」として記載。
2. **ai_keyword_only の catch-all 化**（D4/D7）：rejected 862 件中 577 件がこのカテゴリで、E がほぼゼロの純 Transformation 銘柄（JUKI T=83.6 等）まで除外している。設計意図（AI 言及と改革ストーリーの混線防止）は成立するが、Transformation Core の T 値が「全母集団の最高値層」でないことはレポートで正直に書く。A16 で影響を定量化。
3. **TR の無識別力**：改革開示 Level が全社 1 のため、selection_reason の "TR1" は無情報。最終レポートでは TR を根拠として引用しない。
4. **4350（Buffett Core）が唯一の lite**：Transformation 証拠が最弱の銘柄が中核安定枠にいるが、Buffett Core の選定根拠は Phase1 式（Value×Quality×Safety）であり Transformation スコアではないため、役割設計上の矛盾はない。この論理は moat matrix に明記。

## 結論

修復後の Phase3 は 96 点で PASS。残余は Phase5（A16・ablation 解釈）と Phase7（限界節）で吸収する。
