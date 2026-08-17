# Phase3 v2 現状復元記録（Phase0 監査サマリー）

出典: `outputs/phase3_beyond_buffett_v2/`（正典）、`outputs/phase3_beyond_buffett/`（v1・差分監査用）
実装一次ソース: `scripts/phase3_selection/phase3_v2_pipeline.py`, `phase3_common.py`, `phase3_config.json`, `curated_evidence.csv`

## 1. Final20（v2）と役割構成

| 役割 | 社数 | 銘柄 |
|---|---|---|
| Buffett Core | 5 | 3539 JMHD, 6430 大黒電機, 7803 ブシロード, 9470 学研HD, 4350 メディカルSN |
| Transformation Core | 5 | 5902 ホッカンHD, 9828 元気寿司G, 5233 太平洋セメント, 8037 カメイ, 3863 日本製紙 |
| Emerging Core | 5 | 6368 オルガノ, 6315 TOWA, 6920 レーザーテック, 6526 ソシオネクスト, 5803 フジクラ |
| Dual Moat | 3 | 3697 SHIFT, 6841 横河電機, 9474 ゼンリン |
| Bridge / Diversifier | 2 | 3089 テクノアルファ, 2112 塩水港精糖 |

- セクター: Retail 3 / Machinery 3 / 情報通信 3 / 電機 3 / 卸売 2 / 他6業種各1（上限3遵守）
- テーマ: non_ai 10 / semiconductor 3 / factory_automation 2 / business_data 2 / quality_assurance 2 / optical_communication 1（上限4遵守）
- v1→v2 入替: out {7735, 9612, 1961, 4113, 5603} / in {6526, 5233, 8037, 3863, 2112}。**加えて役割入替2社（3089: Trans→Bridge、9828: Bridge→Trans）が差分表に未記載**

## 2. スコアリング実装（v2）

- Transformation（partial式）: 0.22·ValuationGap + 0.24·CapEff + 0.10·FCFproxy + 0.18·ExecRel + 0.16·QualityTrapRes + 0.10·(Phase2Conf/1.1×100) − ValueTrapPenalty、[0,100] clip
- score_type: full（株主還元+改革開示データあり）／partial（FCFproxy+TQ≥2）／lite。**fullは入力欠損により構造的に到達不能**。Final20 = partial 19 / lite 1（liteは4350=Buffett Core）
- Emerging: 0.18·Intangible + 0.15·Innovation + 0.18·Bottleneck + 0.22·AIExposure + 0.14·DataCustomer + 0.13·TrustSafety + EvidenceBonus − HypePenalty(キーワードのみ=18) − GuardrailPenalty
- Evidence Level母集団分布: TQ{0:52, 1:155, 2:326, 3:667}、TR{1:1200}（**全社1・識別力ゼロ**）、TS{0:53, 1:1147}（FCFプロキシ正の言い換え）、EM{0:600, 1:586, 2:8, 3:6}
- 選定: Top5固定 → Dual 3 → Emerging 5 → Transformation 5 → Bridge 2（各役割スコア降順、hard除外・low_pbr_only・ai_keyword_only・セクター≤3・テーマ≤4ガード）

## 3. Phase0 監査で確定した v2 の欠陥（本ループの修復対象）

| # | 欠陥 | 深刻度 | 修復先 |
|---|---|---|---|
| D1 | **final_evidence_level の役割別ロジック未発火**：evidence_levels() が role 確定前に実行され、全1200行が default=max(TQ,EM)。SHIFT は本来 min(TQ2,EM3)=2 のところ 3、レーザーテック/ソシオネクスト/フジクラ（EM2）も 3 に水増し | 高 | Phase3 で役割確定後の正しい final_evidence_level を再計算し、全 CSV を再生成 |
| D2 | Emerging Level2+（14社）が curated_evidence.csv と完全一致 = **手作業証拠に完全依存**。READINESS の「curated非依存 PASS」は母集団カバレッジの話で実態と乖離 | 高 | Phase3 説明資料・リスク分析で正直に開示。systematic screen は L0/1 どまりであることを明記 |
| D3 | Transformation "full" 到達不能、Final20 は partial 19 / lite 1（Buffett Core の 4350 が唯一の lite） | 中 | fullness の開示を Phase3/7 に転記。4350 は Phase1 指標で選定済みのため選定妥当性は毀損しない旨を明記 |
| D4 | **ai_keyword_only ガードが全役割に適用**され、高Tの純Transformation銘柄（JUKI T=83.6、三機工業 T=82.2 等11社以上が選定Transformation最高値 5902 T=82.0 超）を機械的に除外 | 中 | 設計テンションとして開示＋Phase5 に追加 ablation（A16: ガードをEmerging系役割のみに限定）で影響を定量化 |
| D5 | 配分計画: 全銘柄 target 5% 均一・実消化 47.5%・**5社購入不可**（6920 1単元¥3.84M、6368 ¥1.58M、6841/5233/5803 も¥40万超） | 高 | Phase4 で全面再設計（1株単位を基本、100株単元は感度分析） |
| D6 | ablation の interpretation 列が全15行定数文字列 | 中 | Phase5 で overlap 値に基づく実解釈を再生成 |
| D7 | rejected_candidates のカテゴリが実質5種で、報告プローズの粒度（10種）と乖離。ai_keyword_only が catch-all 化（577/862件） | 中 | Phase3 レビューで注記、Phase7 では実カテゴリのみ記載 |
| D8 | v1→v2差分表に役割入替2社（3089, 9828）未記載 | 低 | 本書で記録済み、Phase3 lineage に転記 |
| D9 | docs/ 配下 md がスタブ（300-400B）で詳細はコードのみ | 中 | 本ループの explain_docs / phase3_explanation_for_report.md で文書化し直す |

## 4. Ablation（v2 実測、修復済み normalize_code ベース）

overlap/20: A1=12, A2=16, A3=13, A4=16, A5=13, A6=15, A7=13, **A8=7（最小・Top100のみ）**, A9=12, A10=15, A11=11, A12=16, A13=16, A14=15, A15=15。
→ 構成を最も動かすのは母集団の広さ（A8/A9）と Buffett固定解除（A11）。Evidence ゲート・ペナルティ類は 13〜16 で中程度。

## 5. Rejected Candidates 監査

存在（862行）。rejection_reason_category: ai_keyword_only 577 / already_represented 221 / distress_or_quality_risk 32 / value_trap_risk 17 / low_pbr_only 15。

## 6. 配分計画（v2、Phase4 で置換予定）

役割ターゲット比を役割内等分 → 全銘柄 5% 均一 → 100株単元仮定で 15社=1単元のみ・5社=購入不可、実投資 ¥2,373,020（47.5%）、残現金 ¥2,626,980。needs_human_verification=True 全行。
