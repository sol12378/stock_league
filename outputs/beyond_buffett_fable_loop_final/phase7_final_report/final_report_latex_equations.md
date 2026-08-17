# 最終論文 数式集（LaTeX ソース）

本ファイルは最終論文（日経 STOCK リーグ様式）に登場する全式の LaTeX ソースである。docx では各式を matplotlib mathtext でレンダリングした画像として「モデル名（引用）」バナー＋式＋変数定義＋図表番号キャプションの式ボックスに収めている。Word で最終整形する場合は本 LaTeX を数式エディタ（挿入→数式）へ入力する。

**LaTeX ルール（要項準拠）**：独立式は番号付き（本文から「図表 II-2」等で参照）、`eqnarray` 不使用、数式中テキストは `\mathrm{}`/`\text{}`、`\max \min \log \exp \arg`、上付き語は `S^{\mathrm{Trans}}`。式の直後に変数定義。添字 $i$ は企業。

---

## Ⅱ．スクリーニングの式

**図表 II-2　B/M（Fama and French, 1993）**
```latex
\mathrm{BM}_i = \frac{BE_i}{ME_i}
```

**図表 II-3　E/P（Basu, 1977）**
```latex
\mathrm{EP}_i = \frac{E_i}{ME_i}
```

**図表 II-4　Gross Profitability（Novy-Marx, 2013）**
```latex
\mathrm{GP}_i = \frac{\mathrm{Revenue}_i - \mathrm{COGS}_i}{\mathrm{TotalAssets}_i}
```

**図表 II-5　Piotroski available signal ratio（Piotroski, 2000）**
```latex
\mathrm{PF}^{\mathrm{avail}}_i = \frac{\sum_{s \in \mathcal{S}_i}\mathbf{1}[\text{signal }s\text{ passes}]}{|\mathcal{S}_i|}
```

**図表 II-6　Sloan Accruals（Sloan, 1996）**
```latex
\mathrm{ACC}_i = \frac{\mathrm{NI}_i - \mathrm{CFO}_i}{\mathrm{TotalAssets}_i}
```

**図表 II-7　60日平均売買代金（流動性）**
```latex
\mathrm{ADV}_{i,60} = \frac{1}{60}\sum_{d=1}^{60} P_{i,d}\,V_{i,d}
```

**図表 II-8　市場パーセンタイル正規化**
```latex
z^{\mathrm{mkt}}_{i,k} = \frac{\mathrm{rank}_{j\in\Omega}(x_{j,k})}{|\Omega|}\bigg|_{j=i}
```

**図表 II-9　正規化コンセンサスタグ**
```latex
\mathrm{Consensus}_i = \sum_{m\in\mathcal{M}}\mathbf{1}\!\left[\mathrm{rank}^{(m)}_i \le N\right],\quad \mathcal{M}=\{\mathrm{mkt},\mathrm{sector},\mathrm{robust\text{-}z},\mathrm{wins\text{-}z}\}
```

**図表 II-11　Transformation Moat Score（設計形）**
```latex
S^{\mathrm{Trans}}_i = 100\left(w_V V_i + w_C C_i + w_R R_i + w_E E_i + w_X X_i + w_Q Q_i\right) - P^{\mathrm{Trap}}_i
```

**図表 II-12　Transformation Moat Score（partial 実装形）**
```latex
S^{\mathrm{Trans,partial}}_i = 0.22 V_i + 0.24 C_i + 0.10 F_i + 0.18 X_i + 0.16 Q_i + 0.10 \Phi_i - P^{\mathrm{Trap}}_i
```

**図表 II-13　Emerging Moat Score**
```latex
S^{\mathrm{Emerg}}_i = 100\left(w_I I_i + w_N N_i + w_B B_i + w_A A_i + w_D D_i + w_T T_i\right) + B^{\mathrm{Evidence}}_i - P^{\mathrm{Hype}}_i - P^{\mathrm{Guard}}_i
```

**図表 II-14　最終 Evidence Level（役割別）**
```latex
L^{\mathrm{final}}_i =
\begin{cases}
\min(L^{TQ}_i, L^{EM}_i) & \text{Dual Moat}\\
L^{EM}_i & \text{Emerging Core}\\
\max(L^{TQ}_i, L^{TS}_i, L^{TR}_i) & \text{Transformation Core}\\
\max(L^{TQ}_i, L^{EM}_i) & \text{その他}
\end{cases}
```

---

## Ⅲ．ポートフォリオ・検証の式

**図表 III-0a　Risk-adjusted Role Allocation（採用案）**
```latex
\omega_i = B_{r(i)}\cdot\frac{\rho_i}{\sum_{j:r(j)=r(i)}\rho_j},\quad \rho_i = \frac{1}{\max(\sigma_i,0.10)}\cdot\ell_i\cdot e_i\cdot c_i
```

**図表 III-0b　単元株調整購入株数**
```latex
q_i = L_i\left\lfloor \frac{B\,\omega_i}{P_i L_i}\right\rfloor
```

**図表 III-2a　Sharpe Ratio（Sharpe, 1966, 1994）**
```latex
\mathrm{Sharpe} = \frac{\bar{r}_p - r_f}{\sigma_p}
```

**図表 III-2b　Maximum Drawdown**
```latex
\mathrm{MDD} = \min_{t}\left(\frac{C_t}{\max_{s\le t} C_s} - 1\right)
```

**図表 III-2c　Jensen's α（Jensen, 1968）**
```latex
\alpha_p = \bar{r}_p - \beta_p\,\bar{r}_m,\quad \beta_p = \frac{\mathrm{Cov}(r_p, r_m)}{\mathrm{Var}(r_m)}
```

**図表 III-2d　Herfindahl–Hirschman Index（集中度）**
```latex
\mathrm{HHI} = \sum_{g}\left(\sum_{i\in g}\omega_i\right)^{2}
```
