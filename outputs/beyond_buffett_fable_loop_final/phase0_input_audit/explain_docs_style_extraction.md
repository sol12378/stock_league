# Explain Docs Style Extraction（既存説明資料のスタイル抽出）

出典: `docs/explain_docs/phase1_buffett_methodology_report_flow_v2.tex`（Phase1）, `docs/explain_docs/phase2_methodology_report_polished.tex`（Phase2）

## 1. ドキュメント構造の型

両 tex 共通：
```
titlepage（守破離の位置づけ図 + このPDFの目的）
→ \section*{まず結果：…}   ← 結論先出しが最大の特徴
→ 目次
→ 本編（なぜこのPhaseが必要か → 基礎 → 式 → 手順 → 結果 → 限界）
→ Appendix A: 変数一覧（longtable）
→ Appendix B: 式別リファレンス
→ Appendix C: 数式組版方針
→ 参考文献
```

## 2. Phase1 tex の章順（要旨）

まず結果（funnel 3,099→2,740→583→146→112→90→77→Top5）→ エグゼクティブサマリー → 読み方 → なぜPhase1が必要か（守破離）→ 簿記と株の基礎 → 式の全体像 → Value（B/M・E/P）→ Quality（GP）→ Financial Strength（Piotroski available）→ Earnings Quality（Sloan）→ Low Distress（Ohlson/Altman/guardrail）→ Liquidity & Anomaly → Value×Quality マトリクス → Top5 の選び方（逐次 tie-break）→ 計算例 → カバレッジ → 最終20社への組み込み → 限界 → 検証式（選定には使わない旨明記）→ 圧縮版。

## 3. Phase2 tex の章順（要旨)

まず結果 → 何を守り何を破るか → 簿記の基礎 → 変えない式 → 使い方の最適化（4正規化）→ Exploratory Weighted Buffett Score → 探索アルゴリズム（Grid/Random/Optuna TPE/NSGA-II）→ TopN 決定（utility）→ 業種分散 HHI → 正規化の揺れ／consensus tag → point-in-time panel と時点外確認 → Formal Top1200 最終監査 → なぜ Buffett を体現できるか → Phase3 への渡し方 → 限界。

## 4. 図表スタイル

- 表キャプション上・図キャプション下、booktabs、`\arraystretch=1.22`
- 図は TikZ 内製（Phase1）または外部 PDF（Phase2、figures/ 配下）
- 本文中で必ず参照（\ref/\eqref）
- keybox（要点）/ warnbox（注意）/ defbox（定義・直感）の3種ボックス

## 5. 本ループの explain_docs への適用

- 各 Phase の `explain_docs/phaseN_explanation_material.md` は「まず結果 → なぜ → 式（4段構成）→ 手順 → 限界」の順で書く。
- フロー図は Mermaid（.mmd）で作成し、tex の TikZ funnel と同じ情報密度（各段の社数）を持たせる。
- 提出論文（Phase7）は募集要項の Word 体裁が正であり、この tex スタイルは**内部説明資料の様式**として使い分ける。
