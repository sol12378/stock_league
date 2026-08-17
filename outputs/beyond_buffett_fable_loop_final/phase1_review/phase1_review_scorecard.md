# Phase1「守」Review Scorecard（loop 1）

採点日: 2026-07-10／採点対象: `outputs/phase1_top5/`（正典）＋ `phase1_final/`・`phase1_buffett_complete/`（過程資産）＋ `docs/explain_docs/phase1_buffett_methodology_report_flow_v2.tex`

## 総合: **96 / 100 → PASS（≥95）**

| 基準 | 配点 | 得点 | 根拠 |
|---|---|---|---|
| 1. 先行研究接続 | 20 | 19 | B/M=Fama-French(1993)、E/P=Basu(1977,1983)、GP=Novy-Marx(2013)、Piotroski(2000)、Sloan(1996)が式レベルで対応。Ohlson(1980)/Altman(1968)は引用のうえ**原式未実装を正直に開示**し simple guardrail で代替。−1: distress guardrail 自体は公刊式ではないため「先行研究式による抽出」の純度がここだけ下がる（開示済みなので軽微） |
| 2. 財務・会計指標の妥当性 | 20 | 19 | 定義は全て正典どおり（GP=売上総利益/総資産、Sloan=(NI−CFO)/平均TA、E/Pは正利益のみ）。カバレッジ開示あり（GP 98.2%）。−1: Piotroski が 6/9 の available 版であり完全な F-Score でない（「available signal score」と正確に命名して開示済みだが、指標としての情報量は原式より低い） |
| 3. Guardrail の透明性 | 20 | 20 | 流動性3段階閾値（300万/1000万円）、distress hard exclude、負債・自己資本フラグ、異常値・一時的利益疑いの各監査CSVが個別に存在。除外件数が数値で追跡可能。ファネル各段の社数（3,099→…→77→5）が完全開示 |
| 4. Buffett Core としての説明力 | 20 | 19 | Top5固定・最終20社の「守る堀Core」枠（20〜25%）として文書化。銘柄別 rationale あり。Value×Quality 同時充足＋逐次tie-break（重み付き合成スコア不使用）が明確。−1: Top5 と sector-adjusted final20 の rank 非連続（9990/8278 のスキップ）の説明が複数文書に分散 → 本ループの説明資料で一元化して修復 |
| 5. レポート転用可能性 | 20 | 19 | phase1_top5_report_section.md と methodology tex が存在し、式・図・限界が揃う。−1: 配当利回りの データ乖離（6430）と look-ahead 注意書きをレポート本文に転記する必要（修復タスク化） |

## 判定

- **Phase1 は「守」として成立**：先行研究式のみ・段階的スクリーニング・Top5固定・guardrail 監査つき。
- 96点の残り4点はすべて**開示済みの限界**または**説明の分散**であり、選定ロジック自体の欠陥ではない。修復は本ループの説明資料（explain_docs/phase1_*）で吸収する。
