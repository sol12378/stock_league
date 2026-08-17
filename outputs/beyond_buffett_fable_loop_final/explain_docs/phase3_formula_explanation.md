# Phase3 式の説明（formula explanation）

様式は Phase1/2 と同じ 4 段構成（導入→式→変数定義→直感）。

## 1. Transformation Moat Score（変わる Moat）

現在の市場評価は低いが，資本効率・還元・改革によって再評価されうる度合いを測る。低 PBR の言い換えではない。

$$
S^{\mathrm{Trans}}_i = 100 \times \left( w_V V_i + w_C C_i + w_R R_i + w_E E_i + w_X X_i + w_Q Q_i \right) - P^{\mathrm{Trap}}_i
\tag{10}
$$

ここで，$V_i$ は評価ギャップ，$C_i$ は資本効率改善，$R_i$ は株主還元，$E_i$ は改革開示，$X_i$ は実行信頼性，$Q_i$ は利益の質・安定性，$P^{\mathrm{Trap}}_i$ はバリュートラップ・ペナルティである。重み初期値は $w_V{=}0.20,\ w_C{=}0.22,\ w_R{=}0.16,\ w_E{=}0.17,\ w_X{=}0.13,\ w_Q{=}0.12$（概念設計係数，±20% 感度分析済み）。

**実装形（partial）**：$R_i$・$E_i$ の構造化開示データが欠損のため，実装は次で運用する。

$$
S^{\mathrm{Trans,partial}}_i = 0.22\,V_i + 0.24\,C_i + 0.10\,F_i + 0.18\,X_i + 0.16\,Q_i + 0.10\,\Phi_i - P^{\mathrm{Trap}}_i
\tag{11}
$$

ここで，$F_i$ は FCF プロキシ（$\mathrm{CFO}_i - \mathrm{CAPEX}_i$ に基づく還元余力の代理），$\Phi_i$ は Phase2 信頼度（$100 \times \mathrm{conf}_i / 1.1$）である。

> **直感**：「安い（$V$）だけでは選ばれない。実際に良くなっている（$C$：3年の ROA・マージン・回転率改善）・約束を守れる（$X$：Piotroski・CFO/NI）・利益が本物（$Q$：低アクルーアル）が揃って初めて高得点になる。罠の兆候（高アクルーアル・営業CF赤字・継続損失）は $P^{\mathrm{Trap}}$ で直接減点する。」

## 2. Emerging Moat Score（生まれる Moat）

産業構造の変化（AI・データセンター・半導体・電力・光通信・自動化・セキュリティ・業務データ・品質保証）によって**これから形成される**競争優位を測る。AI テーマ株の言い換えではない。

$$
S^{\mathrm{Emerg}}_i = 100 \times \left( w_I I_i + w_N N_i + w_B B_i + w_A A_i + w_D D_i + w_T T_i \right) + B^{\mathrm{Evidence}}_i - P^{\mathrm{Hype}}_i - P^{\mathrm{Guard}}_i
\tag{12}
$$

ここで，$I_i$ は無形資産，$N_i$ は技術・イノベーション能力，$B_i$ はボトルネック性・価格決定力，$A_i$ は AI 産業基盤接続，$D_i$ はデータ・顧客基盤，$T_i$ は信頼・安全基盤である。重みは $w_I{=}0.18,\ w_N{=}0.15,\ w_B{=}0.18,\ w_A{=}0.22,\ w_D{=}0.14,\ w_T{=}0.13$。$B^{\mathrm{Evidence}}_i \in \{0,2,4,8\}$ は開示レベルに応じたボーナス，$P^{\mathrm{Hype}}_i$ はキーワードのみの言及への減点（18 点），$P^{\mathrm{Guard}}_i$ は財務ガードレール減点（20 点）である。

> **直感**：「AI と言っただけ（Level 1）ではボーナス +2 に対しペナルティ −18 で**差し引き大幅マイナス**。売上・受注・CAPEX の数量根拠（Level 3）を伴う企業だけが加点される。」

## 3. Evidence Level

$$
L^{\mathrm{final}}_i =
\begin{cases}
\max\left(L^{\mathrm{TQ}}_i,\ L^{\mathrm{TS}}_i,\ L^{\mathrm{TR}}_i\right) & \text{if role}_i = \text{Transformation Core} \\
L^{\mathrm{EM}}_i & \text{if role}_i = \text{Emerging Core} \\
\min\left(L^{\mathrm{TQ}}_i,\ L^{\mathrm{EM}}_i\right) & \text{if role}_i = \text{Dual Moat} \\
\max\left(L^{\mathrm{TQ}}_i,\ L^{\mathrm{EM}}_i\right) & \text{otherwise}
\end{cases}
\tag{13}
$$

ここで，$L^{\mathrm{TQ}}_i$ は変革の定量証拠レベル（0–3），$L^{\mathrm{TR}}_i$ は改革開示レベル，$L^{\mathrm{TS}}_i$ は株主還元証拠レベル，$L^{\mathrm{EM}}_i$ は Emerging 開示レベル（0–3）である。Dual Moat に min を使うのは「両方の Moat に証拠がなければ両立とは言えない」ため。

> **修正記録**：v2 実装では式（13）の役割分岐が役割確定前に評価され全社 default になるバグがあり，本ループで修正した（Final20 分布 L3:19→15，L2:0→4）。選定ゲートには使われていないため銘柄構成への影響はない。
