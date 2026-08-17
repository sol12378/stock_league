# 数式 LaTeX ソース（正典）

本ファイルは学生懸賞論文 DOCX に埋め込んだ全式の LaTeX ソースである。DOCX では pandoc により OMML（Word ネイティブ数式）へ変換して挿入した。Word で再整形する場合はこの LaTeX を数式エディタに入力する。

## （1.1）簿価時価比率 B/M ― 引用式（守：選定使用）

```latex
\mathrm{BM}_i = \frac{BE_i}{ME_i}
```

変数定義：BE_i：自己資本（簿価）；　ME_i：時価総額。値が大きいほど割安（Value）を示す。

## （1.2）益回り E/P ― 引用式（守：選定使用）

```latex
\mathrm{EP}_i = \frac{E_i}{ME_i}
```

変数定義：E_i：当期純利益；　ME_i：時価総額。正で高いほど収益に対して割安。

## （1.3）Gross Profitability ― 引用式（守：選定使用）

```latex
\mathrm{GP}_i = \frac{\mathrm{Revenue}_i - \mathrm{COGS}_i}{\mathrm{TotalAssets}_i}
```

変数定義：Revenue_i：売上高；　COGS_i：売上原価；　TotalAssets_i：総資産。資産効率を伴う収益性（Quality）。

## （1.4）Piotroski available signal ratio ― 改変式・部分実装（守：選定使用）

```latex
\mathrm{PF}^{\mathrm{avail}}_i = \frac{\sum_{s \in \mathcal{S}_i}\mathbf{1}[\text{signal } s \text{ passes}]}{|\mathcal{S}_i|}
```

変数定義：S_i：企業 i で算出可能なシグナル集合；　1[・]：合格シグナルの指示関数。9 指標中 6 指標の部分実装のため、算出可能シグナル中の合格比率で評価する。

## （1.5）Sloan Accruals ― 引用式（守：選定使用）

```latex
\mathrm{ACC}_i = \frac{\mathrm{NI}_i - \mathrm{CFO}_i}{\mathrm{TotalAssets}_i}
```

変数定義：NI_i：当期純利益；　CFO_i：営業キャッシュフロー。アクルーアルが大きいほど利益の質が低い。

## （1.6）60 日平均売買代金（流動性）― 実装式（守：選定使用）

```latex
\mathrm{ADV}_{i,60} = \frac{1}{60}\sum_{d=1}^{60} P_{i,d}\,V_{i,d}
```

変数定義：P_{i,d}：d 日前の終値；　V_{i,d}：出来高。実務上 1,000 万円以上を優先。

## （1.7）簡易 distress ガードレール ― 改変式・原式代替（守：選定使用）

```latex
\mathrm{Distress}_i = \mathbf{1}[\text{債務超過} \ \lor\ \text{連続損失} \ \lor\ \mathrm{CFO}_i < 0]
```

変数定義：Ohlson (1980)・Altman (1968) の原式が入力変数の制約で実装不能なため、債務超過・連続損失・営業CF赤字による簡易ガードレールで代替した。

## （2.1）市場パーセンタイル正規化 ― 実装式（破：候補宇宙形成に使用）

```latex
z^{\mathrm{mkt}}_{i,k} = \frac{\mathrm{rank}_{\Omega}(x_{i,k})}{N_{\Omega}}
```

変数定義：x_{i,k}：指標 k の生値；　Ω：母集団；　N_Ω：母集団サイズ。守の式（1.1）〜（1.6）を変えず、値を市場内順位へ写す。

## （2.2）正規化コンセンサスタグ ― 実装式（破：頑健性確認に使用）

```latex
\mathrm{Consensus}_i = \sum_{m \in \mathcal{M}} \mathbf{1}[\mathrm{rank}^{(m)}_i \le N]
```

変数定義：M＝｛市場, 業種, ロバスト z, ウィンザライズ z｝の 4 正規化方式。4 方式で共通して上位 N に入るほど頑健。

## （3.1）Transformation Moat Score（設計完全形）― 本研究の設計式・選定未使用

```latex
S^{\mathrm{Trans}}_i = 100\,(w_V V_i + w_C C_i + w_R R_i + w_E E_i + w_X X_i + w_Q Q_i) - P^{\mathrm{Trap}}_i
```

変数定義：V_i：評価ギャップ；　C_i：資本効率改善；　R_i：株主還元；　E_i：改革開示；　X_i：実行信頼性；　Q_i：利益の質；　P^{Trap}_i：バリュートラップ罰。設計重み 0.20/0.22/0.16/0.17/0.13/0.12。

## （3.2）Transformation Moat Score（partial 実装形）― 本研究の実装式・選定使用

```latex
S^{\mathrm{Trans,partial}}_i = 0.22\,V_i + 0.24\,C_i + 0.10\,F_i + 0.18\,X_i + 0.16\,Q_i + 0.10\,\Phi_i - P^{\mathrm{Trap}}_i
```

変数定義：F_i：FCF プロキシ（R_i の代替、営業CF−CAPEX>0 で還元余力）；　Φ_i：Phase2 信頼度。E_i（改革開示）は構造化データ欠如のため除外。[0,100] にクリップ。選定に使用した実装式（partial 19 社・lite 1 社）。

## （3.3）Emerging Moat Score ― 本研究の実装式・選定使用

```latex
S^{\mathrm{Emerg}}_i = 100\,(w_I I_i + w_N N_i + w_B B_i + w_A A_i + w_D D_i + w_T T_i) + B^{\mathrm{Evidence}}_i - P^{\mathrm{Hype}}_i - P^{\mathrm{Guard}}_i
```

変数定義：I_i：無形資産；　N_i：イノベーション；　B_i：ボトルネック性；　A_i：AI 基盤接続；　D_i：データ顧客基盤；　T_i：信頼安全基盤。重み 0.18/0.15/0.18/0.22/0.14/0.13。B^{Evidence}≤8 証拠加点；　P^{Hype}：キーワードのみ 18 点罰。

## （3.4）Evidence Level（役割別・スコアと分離）― 実装式（証拠分離に使用）

```latex
L^{\mathrm{final}}_i = \begin{cases} \min(L^{TQ}_i, L^{EM}_i) & \text{Dual Moat} \\ L^{EM}_i & \text{Emerging Core} \\ \max(L^{TQ}_i, L^{TS}_i, L^{TR}_i) & \text{Transformation Core} \\ \max(L^{TQ}_i, L^{EM}_i) & \text{その他} \end{cases}
```

変数定義：L^{TQ}：定量証拠；　L^{TS}：株主還元証拠；　L^{TR}：改革開示；　L^{EM}：Emerging 開示。Level 1＝キーワードのみ、2＝製品/顧客/投資計画、3＝売上/受注/CAPEX 等の数量根拠。

## （4.1）Risk-adjusted Role Allocation ― 実装式（配分に使用・銘柄は不変）

```latex
\omega_i = B_{r(i)} \cdot \frac{\rho_i}{\sum_{j : r(j)=r(i)} \rho_j}, \qquad \rho_i = \frac{\ell_i\, e_i\, c_i}{\max(\sigma_i, 0.10)}
```

変数定義：B_{r}：役割 r の予算（Buffett/Trans/Emerging 0.25、Dual 0.15、Bridge 0.10）；　ρ_i：傾け係数＝流動性 ℓ_i×Evidence e_i×信頼度 c_i÷ボラ σ_i。ω_i>0.08 は 8% に制限。リターン予測は不使用。

## （4.2）単元株調整購入株数 ― 実装式（配分に使用）

```latex
q_i = L_i \cdot \operatorname{floor}\!\left( \frac{B\,\omega_i}{P_i L_i} \right)
```

変数定義：q_i：購入株数；　L_i：売買単位；　B：総予算（500 万円）；　ω_i：目標比率；　P_i：株価；　floor(·)：床関数（切り捨て）。基準 L_i=1（単元未満株）、感度 L_i=100（実単元）。

## （5.1）Sharpe Ratio ― 検証式（銘柄選定に未使用）

```latex
\mathrm{Sharpe} = \frac{\bar{r}_p - r_f}{\sigma_p}
```

変数定義：r̄_p：年率ポートフォリオ収益；　r_f：無リスク金利（約 0）；　σ_p：年率ボラティリティ。in-sample のリスク特性確認であり性能主張ではない。

## （5.2）Maximum Drawdown ― 検証式（銘柄選定に未使用）

```latex
\mathrm{MDD} = \min_{t}\left( \frac{C_t}{\max_{s \le t} C_s} - 1 \right)
```

変数定義：C_t：時点 t の累積指数。ピークからの最大下落率。

## （5.3）Jensen's α ― 検証式（銘柄選定に未使用）

```latex
\alpha_p = \bar{r}_p - \beta_p\,\bar{r}_m, \qquad \beta_p = \frac{\mathrm{Cov}(r_p, r_m)}{\mathrm{Var}(r_m)}
```

変数定義：r_m：TOPIX プロキシ収益；　β_p：市場感応度。β で説明されない超過収益が α_p（in-sample）。

## （5.4）Information Ratio ― 検証式（銘柄選定に未使用）

```latex
\mathrm{IR} = \frac{\bar{r}_p - \bar{r}_b}{\sigma_{p-b}}
```

変数定義：r̄_b：ベンチマーク収益；　σ_{p-b}：トラッキングエラー。直近 1 年 IR は −0.405（負）であり、超過収益を主張しない根拠。

## （5.5）Herfindahl–Hirschman Index（集中度）― 検証式（銘柄選定に未使用）

```latex
\mathrm{HHI} = \sum_{g}\left( \sum_{i \in g} \omega_i \right)^{2}
```

変数定義：g：銘柄・業種・テーマの各グループ。値が大きいほど集中。本研究では銘柄 0.053・業種 0.123・テーマ 0.402。

