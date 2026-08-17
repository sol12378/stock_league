# Phase3 Repair Tasks（loop 1）

Phase0 監査で検出した欠陥 D1〜D9 のうち Phase3 に属するものの処理記録。

| ID | 欠陥 | 処理 | 状態 |
|---|---|---|---|
| D1 | final_evidence_level の役割別ロジック未発火（全社 max(TQ,EM)） | `scripts/phase3_rebuild.py` で役割確定後に再計算。Final20 で 4 社是正（SHIFT・レーザーテック・ソシオネクスト・フジクラ 3→2）、母集団で 7 社。選定ゲート非使用をコード監査で確認済み＝メンバー不変 | **完了** |
| D2 | Emerging L2+ が curated_evidence.csv（14社・手作業）に完全依存 | scorecard・説明資料・リスク分析に明示。「systematic screen は L0/1 まで」と開示 | **完了** |
| D3 | Transformation full 到達不能（還元・改革開示データ欠損）、Final20 = partial 19 / lite 1 | lineage §1.2 で設計式と実装式を分離。lite の 4350 は Phase1 指標で選定済みのため選定妥当性への影響なしと明記 | **完了** |
| D4 | ai_keyword_only ガードが全役割適用で高T銘柄を除外（JUKI T=83.6 等） | 設計テンションとして開示。**Phase5 A16**（ガードを Emerging 系役割に限定した場合の選定変化）で定量化 | Phase5 へ |
| D6 | ablation interpretation が定数文字列 | Phase5 で overlap 値に基づく実解釈を再生成 | Phase5 へ |
| D7 | rejected カテゴリ粒度（実5種 vs プローズ10種）・ai_keyword_only の catch-all 化（577/862） | 本ループ文書では実カテゴリ 5 種のみを記載。catch-all 構造を review_comments に記録 | **完了** |
| D8 | v1→v2 差分に役割入替 2 社（3089, 9828）未記載 | lineage §4 に補記 | **完了** |
| D9 | v2 docs/ がスタブ | explain_docs 4 点（material / flow / formula / moat matrix）を新規作成 | **完了** |

## 意図的に修復しない事項

- **Final20 メンバーの再選定**：D1 は報告バグであり選定ロジックは意図どおり動作していた。ここでメンバーを動かすことこそ「後付け最適化」になる。ai_keyword_only ガードの是非は A16 で影響を示した上で、限界節に記載する。
- **TR / TS の実データ収集**：改革開示・株主還元の構造化データ整備は今後の課題として結論章に記載（数日で捏造なしに整備できる規模ではない）。
