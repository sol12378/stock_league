# Phase5 Review Comments（loop 1）

## 強み
- **ベースライン再現の担保**: アブレーションを回す前に `scripts/phase5_ablation.py` が「全ガード適用のベースが Final20 を 20/20 再現する」ことを assert。A1〜A15 の overlap が v2 CSV と完全一致し、実装同一性を証明。CSV 読み込み時の NaN/bool 退化（`emerging_evidence_category` の NaN→"nan" による theme_cap 誤発火、`bool("False")` 問題）を発見・修正したうえでの一致であり、検証の信頼性が高い。
- **A8 の発見**: overlap 最小（7/20）が Top100 限定であり、「Top1200 に母集団を広げた破の判断」こそが最大の駆動要因だと定量的に示せた。これは設計の後付けでなく前提が効いている証拠。
- **A16 による D4 の解消**: ai_keyword_only ガードを Emerging 系役割に限定しても overlap 16。ガードが過度に拘束的でないことを示しつつ、保守的維持の合理性も説明。
- **誠実性**: 1年 IR 負、curated 依存、L=100 で9社購入不可、テーマ HHI 0.402 を隠さず明記。

## 弱み / 留意
- 全区間 in-sample の限界は構造検査で緩和するのみで、根本解消は将来データ待ち（明記済み）。
- 追加リスク指標（Calmar 等）は任意。図の日本語体裁は Phase7 で確認。

## D系欠陥の解消状況
- D4（ai_keyword_only ガードの緊張）: **A16 で定量化・解消**。
- D6（ablation interpretation 定数文字列）: **overlap＋流入出傾向で全16行を再生成・解消**。
- D2（curated 依存）: リスク分析§4・限界に明記（設計上の限界として受容、今後の課題）。
