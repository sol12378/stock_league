# HANDOFF — BEYOND BUFFETT Fable Loop（引き継ぎ文書）

作成: 2026-07-10（loop 1 途中）／作業ルート: `outputs/beyond_buffett_fable_loop_final/`
状況を一言で: **Phase0〜4 完了（全て95点以上PASS）。Phase5 の実データ検証まで完了し、アブレーション実装の直前で中断。**

---

## 1. 全体設計（変えないこと）

- テーマ「バフェットを超えろ」= 守（Phase1: 完成した Moat を先行研究式で抽出）→ 破（Phase2: 式不変で閾値・分位・通過条件を最適化し候補宇宙形成）→ 離（Phase3: 変わる Moat・生まれる Moat を測定し Final20 構築）。
- 合格条件: 各 Phase レビュー 95 点以上。各 Phase 末尾に scorecard.md / score.json / review_comments.md / repair_tasks.md / pass_fail.md を置く（Phase1〜4 は作成済みなので様式はそれを踏襲）。
- **Final20 のメンバーと役割は確定済み・不変**（バックテストや後知恵での入替は禁止）:
  - Buffett Core 5（Phase1 Top5 固定）: 3539, 4350, 6430, 7803, 9470
  - Transformation Core 5: 5902, 9828, 5233, 8037, 3863
  - Emerging Core 5: 6368, 6315, 6920, 6526, 5803
  - Dual Moat 3: 3697, 6841, 9474 ／ Bridge 2: 3089, 2112

## 2. 正典（source hierarchy）

| 対象 | 正 |
|---|---|
| Phase1 Top5 | `outputs/phase1_top5/phase1_buffett_core_top5.csv` |
| Phase2 母集団 | `outputs/phase2_perfect_final_break/formal_top1200/`（Top2000 は参照群） |
| Phase3 | `outputs/phase3_beyond_buffett_v2/`（v1 は差分監査用） |
| 価格 | `data/processed/prices_daily.parquet`（2021-06-01〜2026-06-01、3,650銘柄） |
| ベンチマーク | TOPIX プロキシ = 1306.T、日経 = ^N225（同 parquet 内） |
| 書式 | `docs/2026年度募集要項.docx`（詳細抽出済み → `phase0_input_audit/report_format_requirements.md`） |

Python は `.venv/bin/python`（pandas / numpy / matplotlib / pyarrow / scipy 利用可）。

## 3. 完了済み Phase とスコア

| Phase | Score | 主な成果 |
|---|---|---|
| 0 | 完了 | 入力棚卸し・欠損監査・書式抽出・v2 の欠陥 D1〜D9 特定（`phase0_input_audit/` 8ファイル） |
| 1 | **96 PASS** | 「守」レビュー＋explain_docs 3点（material / flow.mmd / formula） |
| 2 | **96 PASS** | 「破」レビュー＋explain_docs 3点。distress 重みパラドクスの説明を補完 |
| 3 | **96 PASS** | **D1 バグ修復**: final_evidence_level を役割別に再計算（Final20 分布 L3:19→15, L2:0→4, L1:1。SHIFT・レーザーテック・ソシオネクスト・フジクラが 3→2）。選定ゲート非使用をコード監査で確認済み＝**メンバー不変**。±20% 重み感度も完了（Spearman ρ≥0.994、選定不変）。全 CSV・lineage・explain_docs 4点作成済み |
| 4 | **97 PASS** | 最終配分 = **C案（リスク調整役割配分）** 式(14)。役割 25/25/25/15/10、最大銘柄 7.46%、推定ボラ 18.5%。**L=1（STOCKリーグ規約）で ¥4,949,198 投資・残現金 ¥50,801（消化率 99.0%）**。L=100 感度: 9社購入不可 → 執行リスクとして開示。v2 旧配分（消化率 47.5%）の原因を特定・解消。図3点・表1点作成済み |
| 5 | 途中 | ↓ §4 参照 |

## 4. Phase5 の現在地（ここから再開）

### 完了分
- `scripts/phase5_validation.py` 実行済み。**重要なデータ修理を内包**: 1306.T に未調整の 1:10 分割（2026-03-30）があり、同日以降の価格を×10 補正（2112.T の 2024-01-25 +32.9% は実変動として保持）。
- 結果（`phase5_verification_and_ablation/phase5_validation_summary.json`）:
  - 3年: ポート +30.8%/年 vs TOPIX +24.1% vs 日経 +32.8%、ボラ 21.9%、Sharpe 1.41、Sortino 1.62、MDD −24.9%（TOPIX −23.3%）、β 0.925、Jensen α +7.3%/年、TE 11.1%、IR 0.445
  - 1年: **TOPIX に劣後**（IR −0.405）← 「予測力を主張しない」姿勢の誠実な開示材料として使う
  - 役割寄与（3年 in-sample）: Emerging が支配的（+1.78）、Buffett はほぼゼロ（安定担当）。トップ寄与 = 5803 フジクラ
  - 除外変種: AIテーマ除外→リターン半減・ボラ低下／低PBR（PBR≤1）除外→リターン増だがボラ 35.5%・MDD −44.5%（Value 名柄がリスク緩衝と判明）
  - leave_one_out.csv / exclusion_variants.csv / tables/risk_summary_table.csv / figures/drawdown_chart.png / figures/role_contribution.png 作成済み
- **フレーミング厳守**: ポートは 2026-06 時点データで構築されており全て in-sample。「リスク特性の確認」であり性能主張ではない、を全文書に明記する。

### 未了分（次の作業、この順で）
1. **アブレーション**（中断点）: v2 の `outputs/phase3_beyond_buffett_v2/data/phase3_ablation_results.csv` を読み込み。
   - 列名は `variant`（`ablation_id` ではない！）, description, selected_count, overlap_with_final20, jaccard_with_final20, role/sector/theme_distribution, top_changed_in/out, interpretation。
   - A1〜A15 の `interpretation` が全行定数文字列（欠陥 D6）→ overlap 値で再生成する（例: ≥15「構成は頑健」／10〜14「中程度の入替」／<10「この要素が選定の主要ドライバー」＋ changed_in/out の役割・テーマ傾向を一文）。
   - **A16 を新規追加**（欠陥 D4 の定量化）: ai_keyword_only ガードを Emerging 系役割（Emerging Core / Dual Moat）に限定した場合の再選定。簡易セレクタを実装する: Buffett5 固定 → Dual 3（dual_combined_score 降順）→ Emerging 5（emerging_grade A/B かつ EM≥2、emerging_score 降順）→ Trans 5（transformation_grade A/B、transformation_score 降順）→ Bridge 2（bridge_score 降順）。ガード: base_hard_exclusion（Top5除く）・low_pbr_only・ai_keyword_only・業種上限3・テーマ上限4（non_ai 除く）。**必ず先にガード全適用のベースラインで実際の Final20 が再現できることを確認**してから A16 変種を回す（再現しない場合はその旨を開示して定性記述に切替）。
   - code 照合は必ず normalize_code（str→BOM/.T 除去→zfill(4)）。
   - 出力: `phase5_verification_and_ablation/ablation_results.csv`（A1〜A16）、`ablation_report.md`、`figures/ablation_overlap.png`（overlap 棒グラフ、A8=7 が最小の点を強調）。
2. **risk_analysis.md**: 指定10リスク（Future Moat 偏重／AIテーマ過熱／Trans のバリュートラップ／開示不足による過小・過大評価＝curated 依存 D2／流動性／業種集中／小型株／単元株調整歪み（L=100 で9社購入不可）／バックテスト過信（1年 IR 負を引用）／独自合成式の恣意性（±20%感度で反論））。
3. **performance_validation.md**: summary.json の数値を上記フレーミングで文書化。
4. Phase5 の scorecard / score.json / review_comments / repair_tasks / pass_fail ＋ `explain_docs/phase5_verification_explanation_material.md`（Phase1〜4 の様式踏襲）。
5. **Phase6**: 統合レビュー 7 ファイル（integrated_review_scorecard / repair_tasks / logical_consistency_audit / report_outline_final / figure_table_formula_inventory / reference_integrity_audit / final_pre_report_check）。素材は各 Phase の explanation_for_report と phase0 の書式抽出。参考文献は `docs/phase2_references.md` が要項準拠（英→日）なのでこれを正典に拡張。**注意**: phase1 tex の Sharpe/Jensen が本文使用と bibliography 不一致 → 最終論文では双方向対応を必ず取る。
6. **Phase7**: `final_report.md`（構成は指示書 7.3 の Ⅰ〜Ⅷ＋注＋参考文献、図表 I-1〜VII-2、式は各 explain_docs の (1)〜(15) を再利用）。docx/pdf は pandoc の有無を確認（`which pandoc`）。無ければ md ＋ `final_report_docx_generation_instructions.md` / `final_report_pdf_generation_instructions.md` を出す（要項: 44字×36行・MS明朝9pt・MSゴシック見出し4段階・図表タイトル上部左寄せ・参考文献 MS明朝8pt 英→日・個人名/ゼミ名/謝辞禁止・PDF は表紙氏名を白文字）。
7. README.md / MANIFEST.md / **FINAL_LOOP_READINESS_CHECK.md**（指示書 §7 の全項目 PASS/FAIL）→ `zip -r outputs/beyond_buffett_fable_loop_final.zip outputs/beyond_buffett_fable_loop_final`（元フォルダは削除しない）→ 指示書 §8 の標準出力。

## 5. 既知の落とし穴（次の担当者へ）

- **1306.T の分割補正**は phase5_validation.py 内にしかない。ベンチマークを再利用する新スクリプトを書く場合は同じ補正（2026-03-30 以降 ×10）を必ず入れること。
- v2 の `docs/` 配下 md はスタブ（300〜400B）。中身はコード（`phase3_v2_pipeline.py` / `phase3_common.py`）が一次ソース。
- v2 ablation CSV の列名は `variant`。`ablation_id` で参照すると KeyError（中断直前に踏んだ）。
- Phase4 の B案は役割構成 5/5/5/3/2 では A案（等金額）と数学的に一致する——説明資料で活用済みの論点。
- TR（改革開示レベル）は全1200社=1 で識別力ゼロ。最終論文で TR を選定根拠として引用しない。
- Emerging L2+ は curated_evidence.csv（14社・手作業）に完全依存（D2）。リスク分析・限界節に必ず記載。

## 6. 人間確認事項（FINAL_CHECK に転記するもの）

1. 公式 Word テンプレート（Moodle 配布）が未入手 → 提出前に流し込み必須
2. 提出締切日が要項本文に明示なし → Moodle で確認
3. 要項内の 44字 vs 46字矛盾 → テンプレート実測で確定（本ループは44字×36行で設計）
4. 単元株数 = 全銘柄100株の仮定 → 取引所データで裏取り
5. 6430 の配当乖離（会社予想 4.25% vs トレーリング 0%）
6. 実運用時は単元未満株（S株）利用が前提（L=100 では9社購入不可）

## 7. スコア現況

Phase1: 96 ／ Phase2: 96 ／ Phase3: 96 ／ Phase4: 97 ／ Phase5〜7: 未採点。
進行状態の機械可読版は `logs/loop_state.json`（本引き継ぎと同期済み）。
