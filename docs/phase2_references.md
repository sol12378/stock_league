# BEYOND BUFFETT Phase2 参考文献リスト
## 先行研究式の適用条件最適化・重み最適化・多目的最適化に関する文献

### 作成方針

本ファイルは，青山学院大学経営学会「2026年度学生懸賞論文募集要項」の参考文献表記に合わせ，英語文献と日本語文献に分け，英語文献を先，日本語文献を後に記載する。英語文献は著者姓のアルファベット順，日本語文献は五十音順を原則とする。定期刊行物の論文は「著者名，刊行年，論文タイトル，雑誌名，巻数，ページ」の順に整理する。インターネット文献は「著者名，文献タイトル，サイト名，URL，最新確認年月日」を記す。

本文中で引用する場合は，たとえば以下のように用いる。

- ランダムサーチは，少数の重要なハイパーパラメータを探索する場合，グリッドサーチより効率的になり得る（Bergstra・Bengio，2012）。
- Optuna は define-by-run 型のハイパーパラメータ最適化フレームワークとして提案されている（Akiba et al.，2019）。
- NSGA-II は，多目的最適化において Pareto 解集合を探索する代表的手法である（Deb et al.，2002）。

---

## 英語文献

### 1．Phase1から継続して用いる財務・会計・ファクター投資の基礎文献

Altman, E. I. (1968) Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy. *The Journal of Finance*, 23(4), pp.589-609.

Asness, C. S., Frazzini, A., & Pedersen, L. H. (2019) Quality Minus Junk. *Review of Accounting Studies*, 24, pp.34-112.

Basu, S. (1977) Investment Performance of Common Stocks in Relation to Their Price-Earnings Ratios: A Test of the Efficient Market Hypothesis. *The Journal of Finance*, 32(3), pp.663-682.

Basu, S. (1983) The Relationship between Earnings' Yield, Market Value and Return for NYSE Common Stocks: Further Evidence. *Journal of Financial Economics*, 12(1), pp.129-156.

Fama, E. F., & French, K. R. (1993) Common Risk Factors in the Returns on Stocks and Bonds. *Journal of Financial Economics*, 33(1), pp.3-56.

Fama, E. F., & French, K. R. (2015) A Five-Factor Asset Pricing Model. *Journal of Financial Economics*, 116(1), pp.1-22.

Frazzini, A., Kabiller, D., & Pedersen, L. H. (2018) Buffett's Alpha. *Financial Analysts Journal*, 74(4), pp.35-55.

Jensen, M. C. (1968) The Performance of Mutual Funds in the Period 1945-1964. *The Journal of Finance*, 23(2), pp.389-416.

Markowitz, H. (1952) Portfolio Selection. *The Journal of Finance*, 7(1), pp.77-91.

Novy-Marx, R. (2013) The Other Side of Value: The Gross Profitability Premium. *Journal of Financial Economics*, 108(1), pp.1-28.

Ohlson, J. A. (1980) Financial Ratios and the Probabilistic Prediction of Bankruptcy. *Journal of Accounting Research*, 18(1), pp.109-131.

Piotroski, J. D. (2000) Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers. *Journal of Accounting Research*, 38, Supplement, pp.1-41.

Sharpe, W. F. (1966) Mutual Fund Performance. *The Journal of Business*, 39(1), pp.119-138.

Sharpe, W. F. (1994) The Sharpe Ratio. *The Journal of Portfolio Management*, 21(1), pp.49-58.

Sloan, R. G. (1996) Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings? *The Accounting Review*, 71(3), pp.289-315.

White, H. (2000) A Reality Check for Data Snooping. *Econometrica*, 68(5), pp.1097-1126.

### 2．ハイパーパラメータ最適化・Bayesian Optimization・Optunaに関する文献

Akiba, T., Sano, S., Yanase, T., Ohta, T., & Koyama, M. (2019) Optuna: A Next-generation Hyperparameter Optimization Framework. In *Proceedings of the 25th ACM SIGKDD International Conference on Knowledge Discovery & Data Mining*, pp.2623-2631.

Bergstra, J., Bardenet, R., Bengio, Y., & Kégl, B. (2011) Algorithms for Hyper-Parameter Optimization. In *Advances in Neural Information Processing Systems*, 24, pp.2546-2554.

Bergstra, J., & Bengio, Y. (2012) Random Search for Hyper-Parameter Optimization. *Journal of Machine Learning Research*, 13, pp.281-305.

Brochu, E., Cora, V. M., & de Freitas, N. (2010) A Tutorial on Bayesian Optimization of Expensive Cost Functions, with Application to Active User Modeling and Hierarchical Reinforcement Learning. arXiv, https://arxiv.org/abs/1012.2599（2026年7月8日）

Hutter, F., Hoos, H. H., & Leyton-Brown, K. (2011) Sequential Model-Based Optimization for General Algorithm Configuration. In *Learning and Intelligent Optimization*, pp.507-523.

Kushner, H. J. (1964) A New Method of Locating the Maximum Point of an Arbitrary Multipeak Curve in the Presence of Noise. *Journal of Basic Engineering*, 86(1), pp.97-106.

Mockus, J. (1978) The Application of Bayesian Methods for Seeking the Extremum. In L. C. W. Dixon & G. P. Szegő (Eds.), *Towards Global Optimization*, Vol. 2, pp.117-129, North-Holland.

Snoek, J., Larochelle, H., & Adams, R. P. (2012) Practical Bayesian Optimization of Machine Learning Algorithms. In *Advances in Neural Information Processing Systems*, 25, pp.2951-2959.

### 3．多目的最適化・NSGA-II・進化計算に関する文献

Deb, K. (2001) *Multi-Objective Optimization Using Evolutionary Algorithms*, John Wiley & Sons.

Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002) A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II. *IEEE Transactions on Evolutionary Computation*, 6(2), pp.182-197.

Fonseca, C. M., & Fleming, P. J. (1995) An Overview of Evolutionary Algorithms in Multiobjective Optimization. *Evolutionary Computation*, 3(1), pp.1-16.

Goldberg, D. E. (1989) *Genetic Algorithms in Search, Optimization, and Machine Learning*, Addison-Wesley.

Hansen, N., & Ostermeier, A. (2001) Completely Derandomized Self-Adaptation in Evolution Strategies. *Evolutionary Computation*, 9(2), pp.159-195.

Storn, R., & Price, K. (1997) Differential Evolution - A Simple and Efficient Heuristic for Global Optimization over Continuous Spaces. *Journal of Global Optimization*, 11, pp.341-359.

Zitzler, E., Deb, K., & Thiele, L. (2000) Comparison of Multiobjective Evolutionary Algorithms: Empirical Results. *Evolutionary Computation*, 8(2), pp.173-195.

### 4．Successive Halving・Hyperband・探索効率化に関する文献

Jamieson, K., & Talwalkar, A. (2016) Non-stochastic Best Arm Identification and Hyperparameter Optimization. In *Proceedings of the 19th International Conference on Artificial Intelligence and Statistics*, pp.240-248.

Li, L., Jamieson, K., DeSalvo, G., Rostamizadeh, A., & Talwalkar, A. (2017) Hyperband: A Novel Bandit-Based Approach to Hyperparameter Optimization. *Journal of Machine Learning Research*, 18(185), pp.1-52.

### 5．金融機械学習における過学習対策・検証・安定性評価に関する文献

Bailey, D. H., Borwein, J., de Prado, M. L., & Zhu, Q. J. (2014) Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance. *Notices of the American Mathematical Society*, 61(5), pp.458-471.

Bailey, D. H., & López de Prado, M. (2012) The Sharpe Ratio Efficient Frontier. *Journal of Risk*, 15(2), pp.3-44.

Bailey, D. H., & López de Prado, M. (2014) The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality. *The Journal of Portfolio Management*, 40(5), pp.94-107.

Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2016) The Probability of Backtest Overfitting. *Journal of Computational Finance*, 20(4), pp.39-69.

López de Prado, M. (2018) *Advances in Financial Machine Learning*, John Wiley & Sons.

Romano, J. P., & Wolf, M. (2005) Stepwise Multiple Testing as Formalized Data Snooping. *Econometrica*, 73(4), pp.1237-1282.

White, H. (2000) A Reality Check for Data Snooping. *Econometrica*, 68(5), pp.1097-1126.

### 6．感度分析・安定性指標に関する文献

Jaccard, P. (1901) Étude comparative de la distribution florale dans une portion des Alpes et des Jura. *Bulletin de la Société Vaudoise des Sciences Naturelles*, 37, pp.547-579.

Saltelli, A., Ratto, M., Andres, T., Campolongo, F., Cariboni, J., Gatelli, D., Saisana, M., & Tarantola, S. (2008) *Global Sensitivity Analysis: The Primer*, John Wiley & Sons.

Sobol', I. M. (2001) Global Sensitivity Indices for Nonlinear Mathematical Models and Their Monte Carlo Estimates. *Mathematics and Computers in Simulation*, 55(1-3), pp.271-280.

### 7．実装・ソフトウェア・データ処理に関するインターネット文献

Optuna Contributors. Optuna Documentation, https://optuna.readthedocs.io/（2026年7月8日）

pymoo Developers. pymoo: Multi-objective Optimization in Python, https://pymoo.org/（2026年7月8日）

SciPy Developers. scipy.optimize.differential_evolution, SciPy Documentation, https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.differential_evolution.html（2026年7月8日）

scikit-learn Developers. Model selection and evaluation, scikit-learn Documentation, https://scikit-learn.org/stable/model_selection.html（2026年7月8日）

---

## 日本語文献

青山学院大学経営学会（2026）『2026年度学生懸賞論文募集要項』青山学院大学経営学会．

金融庁「EDINET」，https://disclosure2.edinet-fsa.go.jp/（2026年7月8日）

日本取引所グループ「上場会社情報」，https://www.jpx.co.jp/listing/co-search/（2026年7月8日）

---

## Phase2本文での引用候補

Phase2の本文では，すべての文献を本文中に引用する必要はない。本文で実際に使う場合は，以下の組み合わせが特に重要である。

### ハイパーパラメータ探索の根拠

- Grid Searchだけでは探索空間が粗くなりやすいため，Random Searchを基準線として置く（Bergstra・Bengio，2012）。
- TPEは，過去試行から良い領域を推定して次の試行を選ぶ逐次モデルベース最適化であり，Phase2の重み・閾値探索に適している（Bergstra et al.，2011）。
- Optunaは，TPEやNSGA-IIを含む実験管理フレームワークとして用いる（Akiba et al.，2019）。

### 多目的最適化の根拠

- Phase2では候補数，品質，財務安全性，流動性，業種分散，安定性を同時に評価するため，単一目的の最大化ではなく，多目的最適化が必要である（Deb et al.，2002）。
- NSGA-IIにより，単一の「最良解」ではなく，Pareto解集合として候補ルールを比較できる（Deb et al.，2002；Zitzler et al.，2000）。

### 過学習対策の根拠

- 多数の探索を行うと，偶然よい結果を得た条件を選んでしまう危険があるため，backtest overfittingへの注意が必要である（Bailey et al.，2014）。
- Sharpe Ratioを比較する場合は，選択バイアスや非正規性を補正するDeflated Sharpe Ratioの考え方が有用である（Bailey・López de Prado，2014）。
- 金融データで交差検証を行う場合は，リーケージを避けるためのPurged CVやCombinatorial Purged CVの考え方を参照する（López de Prado，2018）。

### Phase1式との連続性

- Buffett型投資を公開データで近似する際の基礎として，B/M，E/P，Gross Profitability，Piotroski F-Score，Sloan Accruals，Distress指標を用いる（Fama・French，1993；Basu，1977；Novy-Marx，2013；Piotroski，2000；Sloan，1996；Altman，1968；Ohlson，1980）。
- Phase2ではこれらの式の定義を変えず，閾値・分位・重み・候補数を探索することで，「守」を維持しながら「破」を体現する。
