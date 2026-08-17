# 数式 LaTeX ソース（説明論文・正典）

各式は pandoc により OMML（Word ネイティブ数式）へ変換して両文書に挿入。cases 形式を含む。

## （1.0）時価総額（会社全体の値段）

分類：基礎（引用式）

```latex
\mathrm{ME}_i = P_i \times N_i
```

記号：ME_i＝時価総額；P_i＝株価；N_i＝発行済株式数

## （1.1）B/M（株価に対して純資産が何倍か＝割安さ）

分類：引用式（守・選定使用）

```latex
\mathrm{BM}_i = \frac{\mathrm{BE}_i}{\mathrm{ME}_i}
```

記号：BM_i＝簿価時価比率；BE_i＝自己資本（純資産）；ME_i＝時価総額

## （1.2）E/P（株価に対して利益が何%か＝利益面の割安さ）

分類：引用式（守・選定使用）

```latex
\mathrm{EP}_i = \frac{E_i}{\mathrm{ME}_i}
```

記号：EP_i＝益回り；E_i＝当期純利益；ME_i＝時価総額

## （1.3）Gross Profitability（資産をどれだけ効率よく粗利に変えるか＝良い会社か）

分類：引用式（守・選定使用）

```latex
\mathrm{GP}_i = \frac{\mathrm{Revenue}_i - \mathrm{COGS}_i}{\mathrm{TotalAssets}_i}
```

記号：GP_i＝総収益性；Revenue_i＝売上高；COGS_i＝売上原価；TotalAssets_i＝総資産

## （1.4）Piotroski 財務健全性スコア（財務が良い方向に動いているか）

分類：改変式・部分実装（守・選定使用）

```latex
\mathrm{PF}^{\mathrm{avail}}_i = \frac{(\text{合格したシグナル数})}{(\text{計算できたシグナル数})}
```

記号：PF_i＝健全性合格割合；合格シグナル＝各チェックの合格；算出可能数＝計算できた項目数

## （1.5）Sloan アクルーアル（利益が現金の裏づけを持つか＝利益の質）

分類：引用式（守・選定使用）

```latex
\mathrm{ACC}_i = \frac{\mathrm{NI}_i - \mathrm{CFO}_i}{\mathrm{TotalAssets}_i}
```

記号：ACC_i＝アクルーアル；NI_i＝当期純利益；CFO_i＝営業キャッシュフロー

## （1.6）流動性フィルタ（現実に売買できるか）

分類：実装式（守・選定使用）

```latex
\mathrm{ADV}_{i,60} = \frac{1}{60}\sum_{d=1}^{60} P_{i,d}\,V_{i,d}
```

記号：ADV_i＝60日平均売買代金；P_{i,d}＝d日前の終値；V_{i,d}＝d日前の出来高

## （1.7）財務危機ガードレール（長期保有中に倒れないか）

分類：改変式・原式代替（守・選定使用）

```latex
D_i = \begin{cases}1, & \mathrm{BE}_i < 0 \ \text{（債務超過）}\ \text{または}\ (\mathrm{NI}_{i,t}<0\ \text{かつ}\ \mathrm{NI}_{i,t-1}<0\ \text{かつ}\ \mathrm{NI}_{i,t-2}<0)\ \text{（3期連続赤字）}\\0, & \text{上記のいずれにも該当しない}\end{cases}
```

記号：D_i＝危険フラグ；BE_i＝自己資本（純資産）；NI_{i,t}＝当期純利益；t−1, t−2＝前年度・前々年度

## （2.1）市場パーセンタイル正規化（会社同士を同じ物差しで比べる）

分類：実装式（破・候補宇宙形成に使用）

```latex
z^{\mathrm{mkt}}_{i,k} = \frac{\mathrm{rank}_{\Omega}(x_{i,k})}{N_{\Omega}}
```

記号：z_{i,k}＝正規化値；x_{i,k}＝指標kの生値；Ω, N_Ω＝母集団と社数

## （2.2）正規化コンセンサスタグ（物差しを変えても上位に残るか＝頑健性）

分類：実装式（破・頑健性確認に使用）

```latex
\mathrm{Consensus}_i = \sum_{m \in \mathcal{M}} \mathbf{1}\left[\mathrm{rank}^{(m)}_i \le N\right]
```

記号：Consensus_i＝合意度；M＝4つの物差し；N＝上位の基準順位

## （2.3）Phase2 信頼度（その会社の評価をどれだけ信用してよいか）

分類：実装式（破・配分の重みに使用）

```latex
c_i = \mathrm{clip}\big(1 + 0.05\,\text{(頑健)} + 0.03\,\text{(準頑健)} - 0.10\,\text{(外れ値)} - 0.15\,\text{(脆弱)} - \cdots,\ 0,\ 1.1\big)
```

記号：c_i＝Phase2信頼度；clip(・,0,1.1)＝範囲制限；頑健/脆弱 等＝各フラグ

## （3.1）Transformation Moat Score（変わる堀・設計完全形）

分類：本研究の設計式（選定に未使用・付録）

```latex
S^{\mathrm{Trans}}_i = 100\,(w_V V_i + w_C C_i + w_R R_i + w_E E_i + w_X X_i + w_Q Q_i) - P^{\mathrm{Trap}}_i
```

記号：S^Trans＝変わる堀スコア（設計）；R_i, E_i＝株主還元・改革開示；P^Trap＝バリュートラップ罰

## （3.2）Transformation Moat Score（変わる堀・実際に使った実装形）

分類：本研究の実装式（選定に使用）

```latex
S^{\mathrm{Trans,partial}}_i = 0.22 V_i + 0.24 C_i + 0.10 F_i + 0.18 X_i + 0.16 Q_i + 0.10 \Phi_i - P^{\mathrm{Trap}}_i
```

記号：S^{Trans,partial}＝変わる堀スコア（実装）；V_i＝評価ギャップ；C_i＝資本効率改善；F_i＝還元余力(FCF)；Φ_i＝分析信頼度；P^Trap＝バリュートラップ罰

## （3.3）Emerging Moat Score（生まれる堀）

分類：本研究の実装式（選定に使用）

```latex
S^{\mathrm{Emerg}}_i = 100\,(w_I I_i + w_N N_i + w_B B_i + w_A A_i + w_D D_i + w_T T_i) + B^{\mathrm{Evi}}_i - P^{\mathrm{Hype}}_i
```

記号：S^Emerg＝生まれる堀スコア；A_i＝AI基盤接続；B^{Evi}＝証拠加点；P^{Hype}＝過熱ペナルティ

## （3.4）Evidence Level（証拠の強さ・スコアと分けて管理）

分類：実装式（証拠分離に使用）

```latex
L^{\mathrm{final}}_i = \begin{cases}\min(L^{TQ}_i, L^{EM}_i) & \text{（両立型 Dual Moat）}\\L^{EM}_i & \text{（生まれる堀 Emerging Core）}\\\max(L^{TQ}_i, L^{TS}_i, L^{TR}_i) & \text{（変わる堀 Transformation Core）}\\\max(L^{TQ}_i, L^{EM}_i) & \text{（その他）}\end{cases}
```

記号：L^{final}＝最終証拠水準；L^{TQ}＝定量証拠水準；L^{EM}＝新興開示水準；L^{TR}＝改革開示水準

## （4.1）役割予算制約付き・リスク調整配分（選定済み20社へ500万円を配る方法）

分類：実装式（配分に使用・銘柄は不変）

```latex
\omega_i = B_{r(i)} \cdot \frac{\rho_i}{\sum_{j:\,r(j)=r(i)} \rho_j}, \qquad \rho_i = \frac{\ell_i\, e_i\, c_i}{\max(\sigma_i,\,0.10)}
```

記号：ω_i＝最終目標比率；B_{r(i)}＝役割予算；ρ_i＝役割内優先度；ℓ_i＝流動性係数；e_i＝証拠係数；c_i＝信頼度係数；σ_i＝株価変動リスク

## （4.2）単元株調整と8%上限後の再配分（実際に買える株数へ丸める）

分類：実装式（配分に使用）

```latex
q_i = L_i \cdot \operatorname{floor}\!\left( \frac{B\,\omega_i}{P_i L_i} \right)
```

記号：q_i＝購入株数；L_i＝売買単位；B＝総予算；ω_i＝目標比率；floor(・)＝切り捨て

## （5.1）Sharpe Ratio（とったリスクに見合うリターンだったか）

分類：検証式（銘柄選定に未使用）

```latex
\mathrm{Sharpe} = \frac{\bar{r}_p - r_f}{\sigma_p}
```

記号：Sharpe＝シャープ比；r̄_p＝年率リターン；r_f＝無リスク金利；σ_p＝リスク

## （5.2）最大ドローダウン（最悪期にどれだけ下がったか）

分類：検証式（銘柄選定に未使用）

```latex
\mathrm{MDD} = \min_{t}\left( \frac{C_t}{\max_{s \le t} C_s} - 1 \right)
```

記号：MDD＝最大ドローダウン；C_t＝累積価値

## （5.3）Jensen のアルファ（市場変動で説明できない上乗せ分）

分類：検証式（銘柄選定に未使用）

```latex
\alpha_p = \bar{r}_p - \beta_p\,\bar{r}_m, \qquad \beta_p = \frac{\mathrm{Cov}(r_p, r_m)}{\mathrm{Var}(r_m)}
```

記号：α_p＝アルファ；β_p＝ベータ；r_m＝市場リターン

## （5.4）インフォメーション・レシオ（市場に対する超過の安定度）

分類：検証式（銘柄選定に未使用）

```latex
\mathrm{IR} = \frac{\bar{r}_p - \bar{r}_b}{\sigma_{p-b}}
```

記号：IR＝情報比；r̄_b＝ベンチマーク；σ_{p-b}＝トラッキングエラー

## （5.5）集中度指数 HHI（一部に偏っていないか）

分類：検証式（銘柄選定に未使用）

```latex
\mathrm{HHI} = \sum_{g}\left( \sum_{i \in g} \omega_i \right)^{2}
```

記号：HHI＝集中度；g＝グループ；ω_i＝比率

