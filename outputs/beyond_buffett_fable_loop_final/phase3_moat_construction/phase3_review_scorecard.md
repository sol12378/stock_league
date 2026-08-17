# Phase3「離」Review Scorecard（loop 1・修復後）

採点日: 2026-07-10／採点対象: `outputs/phase3_beyond_buffett_v2/`（正典）＋ 本ループ `phase3_moat_construction/`（修復済み成果物）

## 総合: **96 / 100 → PASS（≥95）**

| 基準 | 配点 | 得点 | 根拠 |
|---|---|---|---|
| 1. Transformation 定義・式・証拠 | 20 | 19 | 定義（低PBRではなく「再評価の可能性」）が式に翻訳され、部品は全て Phase1/2 由来（lineage 文書で追跡、再構築誤差 0.0）。株主還元・改革開示の実データ欠損を捏造せず partial/lite に格下げする誠実な設計。±20% 感度で選定不変。−1: full 形が構造的に到達不能で、設計式（10）と実装式（11）の乖離が残る（開示済み） |
| 2. Emerging 定義・式・証拠 | 20 | 19 | 重みが設計初期値と完全一致（0.18/0.15/0.18/0.22/0.14/0.13）。キーワードのみ=18点減点の Hype Penalty と guardrail 減点で「AIテーマ株選定」を構造的に排除。Evidence ボーナスは L3 でも +8 に抑制。−1: **Level2+ の証拠 14 社が curated_evidence.csv（手作業）に完全依存**。systematic screen は L0/1 どまり（開示済み） |
| 3. Evidence Level 分離 | 20 | 19 | 5 系統（TQ/TR/TS/EM/final）が分離され、L1=キーワードのみ／L2=具体性／L3=数量根拠の閾値が定義どおり。**v2 の final_evidence_level バグ（役割別分岐未発火）を本ループで発見・修正**（Final20: L3 19→15、L2 0→4）。−1: TR が全社 1 で識別力ゼロ、TS が FCF プロキシの言い換え（いずれもデータ制約として開示） |
| 4. Role Assignment 妥当性 | 20 | 19 | 基本形どおり 5/5/5/3/2。Buffett Core=Phase1 Top5 固定をコードで検証。セクター上限 3・テーマ上限 4 遵守（Retail/Machinery/情報通信/電機 各3、non_ai 10）。Dual は T×E 両立（min 式）、Bridge は分散役として T 高・E 低銘柄。−1: **ai_keyword_only ガードが全役割に適用**され、選定 Transformation 最高値（T=82.0）を上回る純 Transformation 銘柄 11 社超を機械的に除外（設計テンションとして開示し、Phase5 の A16 で影響を定量化） |
| 5. 先行研究式の再構成としての説明力 | 20 | 20 | lineage 文書が「V=B/M・E/P（Fama-French/Basu）、C=Piotroski 改善思想の連続値化、X=Piotroski・CFO/NI、Q=Sloan・distress、I/B=Novy-Marx GP の転用」と部品単位で追跡し、数値再構築（誤差0.0）で裏づけ。Phase2 スコアは confidence（0.10）としてのみ使用し**最終スコアには不使用** |

## 修復記録（本ループで実施）

| 欠陥 | 修復 |
|---|---|
| D1 final_evidence_level バグ | 役割確定後の再計算で修正。`evidence_levels.csv` に修正値・バグ値・変更フラグを併記 |
| D2 curated 依存 | 本スコアカード・説明資料・リスク分析で明示 |
| D3 full 到達不能 | lineage §1.2 で設計式と実装式を分離明記 |
| D4 ai_keyword_only ガード | 設計テンションとして開示、Phase5 A16 で定量化 |
| D8 v1→v2 役割入替の欠落 | lineage §4 に補記 |
| D9 docs スタブ | explanation material / formula explanation / moat matrix を本ループで新規作成 |

## 判定

Final20 のメンバーは v2 から不変（選定ゲートに final_evidence_level が使われていないことをコード監査で確認）。修復は報告の正確性の回復であり、後付けの銘柄入替ではない。
