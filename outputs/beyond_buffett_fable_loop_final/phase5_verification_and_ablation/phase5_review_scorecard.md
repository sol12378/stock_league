# Phase5 Verification & Ablation Review Scorecard（loop 1）

## 総合: **96 / 100 → PASS（≥95）**

| 基準 | 配点 | 得点 | 根拠 |
|---|---|---|---|
| 1. 検証項目の網羅性 | 20 | 19 | TOPIX/日経比較・Sharpe・Sortino・MDD・Jensen α・β・ボラ・TE・IR・役割/テーマ/業種寄与・HHI・Leave-one-out・トップ寄与除外・AI基盤除外・低PBR除外を実データで算出（3年/1年）。1306.T の未調整分割を検出・補正。−1: Calmar・条件付きVaR等の追加指標は未算出（今後の課題として記載） |
| 2. Ablation の妥当性 | 20 | 20 | A1〜A15 を v2 と同一実装で再現（overlap 完全一致）、**ベースが Final20 を 20/20 再現することを assert で担保**。D6（interpretation 定数）を overlap＋流入出傾向で再生成。**A16（D4 定量化）を新規追加**。normalize_code で全照合 |
| 3. リスク記述の正直さ | 20 | 20 | 指定10リスクを根拠つきで列挙。**1年 IR 負・curated 依存(D2)・L=100 で9社購入不可**を隠さず明記。テーマ HHI 0.402 の高さも開示 |
| 4. 後付け最適化回避 | 20 | 19 | 全区間 in-sample であることを全文書に明記し「性能主張ではない」と繰り返す。銘柄はバックテストで入替えない。−1: in-sample の限界は out-of-sample 検証（将来データ）でしか根本解消せず、本ループでは構造検査に留まる旨を明示 |
| 5. レポート転用可能性 | 20 | 18 | performance_validation / ablation_report / risk_analysis と図3点・表1点が Ⅶ章にそのまま転用可能な粒度。explain_docs 素材も作成。−2: 図の日本語ラベル体裁は Phase7 docx 転記時に最終確認、Calmar 等の追加は任意 |

## 判定
PASS。検証は「後付け最適化ではなくリスク確認」として位置づき、in-sample の限界と 1年 IR 負を誠実に開示。アブレーションは母集団の広さ（A8）を最大駆動要因と特定し、単一要素・単一テーマ依存を定量的に否定した。
