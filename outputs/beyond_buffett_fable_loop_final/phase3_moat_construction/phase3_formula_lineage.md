# Phase3 Formula Lineage（式の系譜：先行研究 → Phase1/2 → Phase3）

Phase3 の 2 つの合成スコアは，新規のブラックボックスではなく，**Phase1 の先行研究式と Phase2 の正規化部品の再構成**である。本書はその系譜を式レベルで追跡し，再構築検証（実装との誤差 0.0）で裏づける。

## 1. Transformation Moat Score（変わる Moat）

### 1.1 設計式（概念形）

$$
S^{\mathrm{Trans}}_i = 100 \times \left( w_V V_i + w_C C_i + w_R R_i + w_E E_i + w_X X_i + w_Q Q_i \right) - P^{\mathrm{Trap}}_i
\tag{10}
$$

ここで，$V_i$ は評価ギャップ，$C_i$ は資本効率改善，$R_i$ は株主還元，$E_i$ は改革開示，$X_i$ は実行信頼性，$Q_i$ は利益の質・安定性，$P^{\mathrm{Trap}}_i$ はバリュートラップ・ペナルティである。設計重み初期値は $w_V{=}0.20,\ w_C{=}0.22,\ w_R{=}0.16,\ w_E{=}0.17,\ w_X{=}0.13,\ w_Q{=}0.12$。

### 1.2 実装式（データ制約下の partial 形）

株主還元（$R_i$）・改革開示（$E_i$）の**正式開示フィールドが入力データに存在しない**（配当方針・自社株買い・ROIC目標・PBR方針等が欠損）。捏造を避けるため，実装は次の partial 形とした：

$$
S^{\mathrm{Trans,partial}}_i = 0.22\,V_i + 0.24\,C_i + 0.10\,F_i + 0.18\,X_i + 0.16\,Q_i + 0.10\,\Phi_i - P^{\mathrm{Trap}}_i
\tag{11}
$$

ここで，$F_i$ は FCF プロキシスコア（$R_i$ の代理：営業CF−CAPEX が正なら還元余力ありとみなす），$\Phi_i$ は Phase2 confidence（$100 \times \mathrm{conf}_i / 1.1$）。[0,100] にクリップ。

| 設計変数 | 実装 | Phase1/2 由来の部品 |
|---|---|---|
| $V_i$ 評価ギャップ | valuation_gap_score | **B/M スコア・E/P スコア**（Fama-French 1993 / Basu 1977 の正規化版）の合成 |
| $C_i$ 資本効率改善 | capital_efficiency_improvement_score | ΔROA・ΔROE・Δ営業マージン・Δ粗利マージン・Δ回転率・Δレバレッジの3年変化（**Piotroski 2000 の改善シグナル思想の連続値化**） |
| $R_i$ 株主還元 | **FCF プロキシで代替**（$F_i$） | 営業CF−CAPEX（Sloan 1996 と同じ CFO 系データ） |
| $E_i$ 改革開示 | **データ欠損のため partial 形から除外**（TR level は全社1で識別力なし） | — |
| $X_i$ 実行信頼性 | execution_reliability_score | **Piotroski available シグナル**・CFO/NI 比 |
| $Q_i$ 利益の質 | quality_trap_resistance_score | **Sloan Accruals**・distress 安全度・流動性信頼度 |
| $P^{\mathrm{Trap}}_i$ | value_trap_penalty | 高 Sloan・負CFO・継続損失・異常値フラグ（Phase2 guardrail の再利用） |

**score_type**: full（$R,E$ の実データあり）／partial（FCF プロキシあり かつ TQ≥2）／lite。入力欠損により **full は構造的に到達不能**。Final20 は partial 19 / lite 1（lite は 4350 のみ＝Buffett Core であり Phase1 指標で選定済みのため選定妥当性は毀損しない）。

### 1.3 検証

- 式（11）を部品列から再構築した値と実装出力の**最大絶対誤差 0.0**（`phase3_rebuild_summary.json`）。
- 重み ±20%（再正規化）の感度分析：1,200 社の順位の Spearman ρ 最小 **0.9973**、選定 Transformation Core 5 社は全 12 バリアントで適格プール上位 5 を維持（`weight_sensitivity_pm20.csv`）。重みは**事後リターン最適化ではなく概念上の設計係数**であり，±20% の摂動で選定が変わらないことを確認した。

## 2. Emerging Moat Score（生まれる Moat）

### 2.1 設計式＝実装式（重みは設計初期値どおり）

$$
S^{\mathrm{Emerg}}_i = 100 \times \left( w_I I_i + w_N N_i + w_B B_i + w_A A_i + w_D D_i + w_T T_i \right) + B^{\mathrm{Evidence}}_i - P^{\mathrm{Hype}}_i - P^{\mathrm{Guard}}_i
\tag{12}
$$

重み：$w_I{=}0.18,\ w_N{=}0.15,\ w_B{=}0.18,\ w_A{=}0.22,\ w_D{=}0.14,\ w_T{=}0.13$（設計初期値と実装が一致）。

| 変数 | 実装 | 由来の部品 |
|---|---|---|
| $I_i$ 無形資産 | intangible_capital_score | R&D/売上比・粗利マージン力（**Novy-Marx 2013 の GP を無形資産の代理へ転用**） |
| $N_i$ 技術・イノベーション | innovation_capacity_score | R&D 強度・従業員成長プロキシ |
| $B_i$ ボトルネック性・価格決定力 | bottleneck_pricing_power_score | 0.35×粗利マージン + 0.35×GP + 0.30×開示強度 |
| $A_i$ AI 産業基盤接続 | ai_infrastructure_exposure_score | 開示証拠強度（カテゴリ横断） |
| $D_i$ データ・顧客基盤 | data_customer_base_score | 開示強度 × カテゴリ（business_data / QA / security） |
| $T_i$ 信頼・安全基盤 | trust_safety_infrastructure_score | 開示強度 × カテゴリ（QA / security / FA / 半導体 / 精密加工） |
| $B^{\mathrm{Evidence}}_i$ | Level {0,1,2,3}→{0,2,4,8} | Evidence Level ボーナス |
| $P^{\mathrm{Hype}}_i$ | キーワードのみ＝18 点減点 | AI テーマ株化の防止 |
| $P^{\mathrm{Guard}}_i$ | hard exclusion 該当＝20 点減点 | Phase2 guardrail の再利用 |

### 2.2 検証

- 再構築の最大絶対誤差 0.0。重み ±20% で Spearman ρ 最小 **0.9937**，EM≥2 プール上位 8 の構成は全 12 バリアントで不変。

## 3. Evidence Level（5 系統に分離）

| 系統 | 値域 | 定義 |
|---|---|---|
| transformation_quant_evidence_level（TQ） | 0–3 | 3年財務改善指標の本数による定量証拠 |
| transformation_reform_disclosure_level（TR） | 0/1 | 改革開示の有無（**現状全社 1＝識別力なし。データ欠損の正直な帰結として開示**） |
| transformation_shareholder_return_evidence_level（TS） | 0–2 | 実装では FCF プロキシ正＝1（正式な還元開示ではない旨を明示） |
| emerging_disclosure_level（EM） | 0–3 | L1=キーワードのみ／L2=製品・用途・顧客・投資計画の具体性／L3=売上・受注・CAPEX 等の数量根拠 |
| final_evidence_level | 0–3 | **役割別**：Transformation Core = max(TQ,TS,TR)／Emerging Core = EM／Dual Moat = min(TQ,EM)／その他 = max(TQ,EM) |

### 3.1 v2 実装バグの修正（本ループ D1）

v2 では final_evidence_level の役割別分岐が**役割確定前に実行され未発火**（全社 default=max(TQ,EM)）。本ループで役割確定後に再計算した結果：

- Final20 の分布：バグ版 {L3:19, L1:1} → **修正版 {L3:15, L2:4, L1:1}**
- 変更 4 社：SHIFT 3→2（min(TQ2,EM3)）、レーザーテック・ソシオネクスト・フジクラ 3→2（EM=2）
- **選定への影響なし**：選定ゲートは emerging_disclosure_level と grade を使用し，final_evidence_level は報告専用であることをコード監査で確認済み。

## 4. v1→v2 の系譜補記（D8）

メンバー入替 5 社（out: 7735, 9612, 1961, 4113, 5603／in: 6526, 5233, 8037, 3863, 2112）に加え，**役割入替 2 社**（3089 Transformation→Bridge、9828 Bridge→Transformation）があった。v2 差分レポートには後者が明記されていないため本書で補記する。
