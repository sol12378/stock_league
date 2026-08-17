# Phase6 論理整合性監査

Phase1〜5 を横断し、主張・数値・定義の矛盾を洗い出す。**発見した不整合はこのループで修正済み or 開示済み**。

## 1. 数値整合（クロスチェック）

| 項目 | 値 | 出典 | 整合 |
|---|---|---|---|
| Phase1 Top5 | 3539/4350/6430/7803/9470 | phase1_explanation §4, allocation_final | ✔ 全文書一致・固定 |
| Phase2 正式母集団 | Top1200 | phase2_explanation §3, source_hierarchy | ✔ Top2000 は参照群と明記 |
| Final20 役割構成 | 5/5/5/3/2 | phase3 §5, allocation_final | ✔ |
| Final Evidence Level 分布 | L3=15, L2=4, L1=1 | phase3 §4, evidence_levels.csv | ✔ D1修復後で一致 |
| Transformation score_type | partial 19 / lite 1 | phase3 §2, formula_lineage | ✔ |
| 低PBRのみ除外 | 15社 | phase3 §2・§6 | ✔ |
| 配分最終案 | C案（式14）役割 25/25/25/15/10 | phase4 | ✔ |
| 執行（L=1） | ¥4,949,198・消化率99.0% | phase4 | ✔ |
| 検証 3年 Sharpe/α/β | 1.41 / +7.3% / 0.925 | phase5 summary.json | ✔ |
| 1年 IR | −0.405（負） | phase5 | ✔ 誠実開示 |

## 2. このループで修正した不整合

- **[修正済] 感度分析 Spearman ρ の過大記載**: `phase3_explanation_for_report.md` が「ρ ≥ 0.997」と記載していたが、`weight_sensitivity_pm20.csv` の Emerging 最小は 0.9937。→「Transformation 最小 0.997・Emerging 最小 0.994」に修正。formula_lineage（0.9973＝Transformation のみ）とも両立。
- **[解消] D6 ablation interpretation 定数**: 全16行を overlap＋流入出傾向から再生成（Phase5）。
- **[解消] D4 ai_keyword_only ガードの緊張**: A16 で定量化（overlap 16、過度に拘束的でない）。

## 3. 開示済みの構造的限界（矛盾ではなく設計制約）

- **Transformation full 形は到達不能**: 株主還元・改革開示の構造化データが入力に存在せず、partial 形（式11）で運用。formula_lineage・phase3 §2・risk §10 で一貫開示。
- **TR（改革開示レベル）全社=1**: 識別力ゼロ。A15（Reform Evidence 除去）が頑健（overlap 15）なのはこのため。**最終論文で TR を選定根拠として引用しない**方針を徹底。
- **Emerging L2+ は curated 依存（D2, 14社）**: 過小評価リスクとして phase3 §4・risk §4 に明記。
- **全区間 in-sample**: 検証は性能主張でなくリスク確認。1年 IR 負をあえて引用。

## 4. 定義の一貫性（キーメッセージ）

- 「Transformation は低PBRではない」: 定義（phase3 §2）＋ `low_pbr_only_flag` 選定ゲート ＋ アブレーション（低PBR除外変種でボラ悪化）の3層で担保。✔
- 「Emerging は AI テーマ株ではない」: 定義（§3）＋ Theme Hype Penalty ＋ Evidence Level≥2 要求 ＋ A16（ガード検証）で担保。✔
- 「Phase2 スコアを最終スコアに使わない」: phase2 §4 明記、Phase3 はコード監査で選定ゲート非使用を確認。✔
- 「守・破・離」: Phase1 式不変／Phase2 式不変・使い方最適化／Phase3 時間軸拡張。アブレーション A8/A1/A2/A11 が各段の効きを定量裏づけ。✔

## 5. 残存事項（人間確認・矛盾なし）
公式 Word テンプレート未入手、44/46字矛盾、単元株100株仮定、6430 配当乖離、S株前提。→ `final_pre_report_check.md` と FINAL_LOOP_READINESS_CHECK に転記。
