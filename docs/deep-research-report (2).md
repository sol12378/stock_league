# BEYOND BUFFETT Phase1再設計レポート

## エグゼクティブサマリー

本レポートの結論は明確です。Phase1（守）は、**「バフェットの投資行動のうち、公開データで再現できる部分だけ」を抽出し、先行研究の既成式だけで組み立てる**のが最も筋がよい設計です。Frazzini, Kabiller, Pedersen は、Buffett の超過成果のかなりの部分を「**割安・安全・高品質の株を、安定的なレバレッジで長く保有したこと**」で説明できると示しましたが、学校レポートとして再現できるのはこのうち **cheap, safe, high-quality stocks** の部分であり、保険フロートという低コスト負債、私企業買収、経営者面談、交渉力、税繰延べ、ガバナンス介入は再現できません。したがって Phase1 は、**Value × Quality × Financial Strength × Low Distress** を、公開財務データで忠実に近似する段階と位置づけるべきです。citeturn41view1turn41view2turn41view3

独自重み付き合成式を避けるべき理由も、方法論的にははっきりしています。Piotroski は F-Score を**9つの二値シグナルの単純合計**として提示し、複雑な年次推定や恣意的重み付けを避ける「実装可能で頑健な fundamental analysis」の形を示しました。Fama-French は**事前に定義されたポートフォリオソート**で HML・RMW・CMA を構成し、Asness, Frazzini, Pedersen は**論文で公開された z-score 合成**として QMJ を提示しています。つまり、Phase1 では「独自の重み」ではなく、**論文に埋め込まれた既成の合成法、二値合計法、または分位ソート**を使うのが最も学術的に整合的です。citeturn37view0turn18view1turn14view0turn14view1

採用すべき中心式は、**QMJ Quality、Gross Profitability、B/M と E/P、Piotroski F-Score、Sloan Accruals、Ohlson O-Score、Altman Z-Score**です。これらはそれぞれ、Buffett 的な「良い会社」「会計の質」「合理的な価格」「破綻しにくさ」を分担して測ります。いっぽうで、**Markowitz 分散、Sharpe Ratio、Jensen’s Alpha** は、選定式ではなく**検証式**として使うのが適切です。**HML・RMW・CMA**は理論的な土台として重要ですが、Phase1 の実装では **B/M、営業採算性、資産成長率**という元の企業属性で使う方が解釈可能性が高いです。**Beneish M-Score** と **Hou-Xue-Zhang の q-factor** は研究上は有用ですが、Phase1 の主軸に入れると目的が「Buffett Proxy」から「異常収益の包括説明」にずれやすいため、採用しても補助的・検証的に留めるべきです。citeturn16view1turn8view2turn10view0turn25view0turn26search0turn40search2turn42view0

最終設計としては、**金融・保険・銀行を主スクリーニングから除外**し、非金融の共通株について、まず **Value で一次選別**し、次に **Quality と Profitability で絞り込み**、さらに **F-Score、Accruals、Distress で除外**し、最後に **Quality × Value の二重ソートの上位セルから20社を等金額配分**する案を推奨します。これは独自重みを使わず、しかも「素晴らしい会社を妥当な価格で買う」という Buffett の守の部分を、査読研究の枠内で最も自然に再現できます。citeturn41view2turn7search4turn18view1turn16view4turn8view2

## Phase1の設計思想

Phase1 の目的は、Buffett の全体像を再現することではありません。再現すべきなのは、**上場株の中から、公開財務データだけで観測できる「完成された堀」の痕跡**です。Frazzini, Kabiller, Pedersen は、Buffett のパフォーマンスが、標準的な市場・サイズ・バリュー要因だけでは説明し切れなくても、**BAB と QMJ を加えると alpha が大きく縮小し、彼が safe, high-quality, value stocks を買っていたことが重要**だと示しました。したがって Phase1 における Buffett 型投資の分解は、少なくとも **Value、Quality、Profitability、Cash Flow Quality、Financial Strength、Low Distress** の六つに整理するのが妥当です。citeturn41view1turn41view2

このとき、**Future Moat、AI 関連テキスト、政策保有株縮減、経営計画テキスト解析、Transformation Score** を Phase1 に入れない判断は、単なる保守性ではなく、研究設計上の合理性があります。これらは将来の競争優位や改革余地に関する情報であり、Phase1 のテーマである「すでに観測可能な優良性」から一歩先に出た要素です。Phase1 を**完成された堀の観測**に限定し、Phase2 以降で**未来の堀・変化の堀**を扱う構成は、守・破・離の切り分けとして筋が通っています。Frazzini らの Buffett 解釈も、まずは cheap / safe / high-quality という既観測の特徴から説明しており、この順序は学術的にも自然です。citeturn41view2turn41view3

独自の合成式を避ける理由は、**学術的な再現可能性**にあります。たとえば `0.35 PROF + 0.25 CF + 0.20 STAB + 0.20 COMP` のような式は、係数の意味が研究史に根差していません。これに対して QMJ は、**profitability, growth, safety, payout を rank-z-score 化して統合する**という、論文内で定義済みの合成法です。Piotroski F-Score も、9 指標の単純合計という明示的な構造を持っています。Fama-French の HML、RMW、CMA は、企業属性を**2×3 ポートフォリオソート**で要因化します。つまり Phase1 では、「合成をしてはいけない」のではなく、**自分で係数を決めた合成をしてはいけない**のであり、**論文が定義した合成法・ソート法はむしろ積極的に使うべき**です。citeturn18view1turn17view0turn37view0turn14view0turn14view1

再現できる範囲と再現できない範囲も、本文で明示した方が良いです。再現できるのは、**財務諸表に表れた高収益性、低 accruals、改善された財務体質、割安性、低 distress**です。再現できないのは、**経営者の能力評価、保険フロートの調達、非公開企業買収、税の繰延べ、長期の関係資本、交渉による優位性**です。したがって Phase1 は「Buffett そのもの」ではなく、**Buffett Proxy Portfolio** です。この言い方なら、過剰な一般化を避けつつ、研究としての位置づけが明確になります。citeturn41view1turn41view2turn41view3

## 先行研究式一覧表

### 選定式として中核に据えるべき式

| 論文名・著者・年・出所 | 式の正確な形 | 主要変数定義 | 何を測るか・実証結果の要約 | Buffett型投資との対応 | 日本株3,299社への注意 / 金融業適用 / データ可否 | Phase1での位置づけ |
|---|---|---|---|---|---|---|
| **Quality Minus Junk** — Asness, Frazzini, Pedersen, 2019, *Review of Accounting Studies*（WP版定義を使用） | \(z(x_i)=\frac{r_i-\mu_r}{\sigma_r}\)。Profitability \(= z(z_{gpoa}+z_{roe}+z_{roa}+z_{cfoa}+z_{gmar}+z_{acc})\)。Growth, Safety, Payout も同様に合成し、Quality は4 proxy の平均。QMJ は高 quality 2ポートフォリオ平均 − junk 2ポートフォリオ平均。 | GPOA, ROE, ROA, CFOA, GMAR, ACC, 5年成長、BAB, IVOL, LEV, O-Score, Z-Score, EVOL, EISS, DISS, NPOP。 | 高品質株は高い risk-adjusted returns を示し、QMJ は米国・国際サンプルで強い alpha を持ち、情報比率 1 超の結果も報告。citeturn17view0turn19view1turn17view1 | 「優良企業を買う」の最も包括的な公開データ proxy。特に safe / quality / payout は Buffett 解釈に近い。citeturn41view2 | フル実装には5年履歴と四半期/年次の安定データが必要。金融はレバレッジや安全性の意味が異なるため原則除外。EDINET◎ / JPX△ / yfinance△。citeturn27view0turn45view1turn44search3 | **採用**。ただし主に非金融の quality 主軸として使う。 |
| **The Other Side of Value: Gross Profitability** — Novy-Marx, 2013, *Journal of Financial Economics* | \(GP/A=(REVT-COGS)/AT\) | Revenue, cost of goods sold, total assets。 | Gross profitability は将来収益率を予測し、value と組み合わせた 50/50 戦略は年率 Sharpe 0.90。double sort でも profitability spread が有意。citeturn16view1turn16view4turn16view0 | 「堀がすでに収益率に現れている会社」を捉える、最も透明な単変量 quality 指標。 | 原論文は金融を除外。日本では売上原価定義の整合、IFRS と日本基準の表示差、総資産の最新時点統一に注意。EDINET◎ / JPX△ / yfinance△。citeturn45view1turn43search3turn44search3 | **採用**。QMJ を補強する単純で強い profitability anchor。 |
| **Common Risk Factors / 5-Factor Model** — Fama & French, 1993 *JFE* / 2015 *JFE* | 3因子回帰: \(R_{it}-R_{ft}=a_i+b_i(R_{Mt}-R_{ft})+s_iSMB_t+h_iHML_t+e_{it}\)。5因子回帰: \(R_{it}-R_{ft}=a_i+b_i(R_{Mt}-R_{ft})+s_iSMB_t+h_iHML_t+r_iRMW_t+c_iCMA_t+e_{it}\)。HML, RMW, CMA は 2×3 ソートで構成。citeturn35view4turn35view0turn14view0 | HML: high B/M – low B/M。RMW: robust OP – weak OP。CMA: conservative Inv – aggressive Inv。OP=\((Revenue-COGS-IntExp-SG\&A)/BE\)。Inv=\((TA_{t-1}-TA_{t-2})/TA_{t-2}\)。citeturn14view0turn14view3turn15view0 | Size・Value・Profitability・Investment の平均収益率パターンを説明。5因子では HML の冗長性が報告されるが、B/M・OP・Inv の企業属性そのものは依然有力。citeturn8view9turn35view4 | Buffett の「reasonable price」と「収益性・保守的投資」を学術要因で接続。 | 日本株では因子時系列は**検証用**、株式選定では B/M・OP・Inv の元属性を使う方が解釈しやすい。金融は OP / Inv の意味が弱い。Ken French library に日本ポートフォリオあり。citeturn13view0turn14view0 | **部分採用**。HML logic は採用、RMW/CMA は主に benchmark / robustness。 |
| **Value Investing** — Piotroski, 2000, *Journal of Accounting Research* | \(F\text{-}Score=FROA+F\Delta ROA+FCFO+F\text{-}ACCRUAL+F\Delta MARGIN+F\Delta TURN+F\Delta LEVER+F\Delta LIQUID+EQOFFER\) | 9つの binary signals。ROA>0, CFO>0, ΔROA>0, CFO>ROA, leverage低下, liquidity改善, equity発行なし, gross margin改善, asset turnover改善。citeturn12view5turn38view0turn38view4 | 高BM株の中で財務的に強い企業を選別すると平均リターンが少なくとも年 7.5% 改善、winner-short loser で年 23% の結果。citeturn8view2 | 「割安な中でも良い会社」を選ぶ Buffett 的発想に最も近い実装。 | 会計制度差はあるが EDINET データで再現しやすい。current ratio や asset turnover を使うため金融は不適。EDINET◎ / JPX△ / yfinance△。citeturn38view0turn38view3turn43search3 | **採用**。Value 内部の quality filter として非常に相性が良い。 |
| **Do Stock Prices Fully Reflect...** — Sloan, 1996, *The Accounting Review* | \(Accruals=\frac{(\Delta CA-\Delta Cash)-(\Delta CL-\Delta STD-\Delta TP)-Dep}{AvgTA}\)、\(CFO=Earnings-Accruals\) | Δ current assets, cash, current liabilities, short-term debt, taxes payable, depreciation, average total assets。citeturn12view0turn11view1 | accrual component は cash flow component より持続性が低く、高 accrual firms は将来の負の abnormal return を示す。citeturn10view0turn11view1 | 会計の質と earnings quality を測る。Buffett 的な「数字の質」の proxy。 | CFO 開示が必要。IFRS/日本基準でも取得可能だが分類差に注意。金融の accrual 構造は別物。EDINET◎ / JPX△ / yfinance△。citeturn43search3turn44search3 | **採用**。除外または tie-break に向く。 |
| **Investment Performance of Common Stocks in Relation to Their Price-Earnings Ratios / Earnings’ Yield and the Size Effect** — Basu, 1977 *Journal of Finance* / 1983 *JFE* | \(E/P = \frac{\text{trailing 12-month EPS}}{P}\) | 直近12か月 EPS / 年初株価。citeturn34view0 | 高 E/P ポートフォリオは beta だけでは説明しきれない高い収益率を示し、Basu 1983 ではサイズ効果は E/P 効果に比べ二次的と報告。citeturn34view0 | Buffett の「価格に対して利益が安い」を最も素朴に表す尺度。 | 日本では赤字企業に不適用。異常値処理が必須。E/P は B/M と併用した方が安定。EDINET◎ / JPX○ / yfinance○。citeturn34view0turn47search1turn44search3 | **採用**。Value のサブ軸として B/M と併用。 |

### 除外条件または補助制御として使うべき式

| 論文名・著者・年・出所 | 式の正確な形 | 主要変数定義 | 何を測るか・実証結果の要約 | Buffett型投資との対応 | 日本株3,299社への注意 / 金融業適用 / データ可否 | Phase1での位置づけ |
|---|---|---|---|---|---|---|
| **Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy** — Altman, 1968, *Journal of Finance* | 原式: \(Z=.012X_1+.014X_2+.033X_3+.006X_4+.999X_5\)。現代的な小数比率表記では \(Z=1.2X_1+1.4X_2+3.3X_3+0.6X_4+1.0X_5\)。\(X_1\)=WC/TA, \(X_2\)=RE/TA, \(X_3\)=EBIT/TA, \(X_4\)=MVE/TL, \(X_5\)=Sales/TA。citeturn25view0turn21search0 | 流動性・累積収益力・収益力・市場評価・回転率。 | 原論文は破綻企業33社と非破綻33社の公開製造業を分離。後年に safe/grey/distress の閾値が広く使われる。citeturn25view0turn21search0 | Buffett の「永久資本毀損を避ける」を測る distress filter。 | 原標本は**公開製造業**。非製造・金融にそのまま使わない。日本株では絶対閾値より rank-based 除外が無難。EDINET◎ / JPX△ / yfinance△。citeturn25view0turn21search0turn43search3 | **採用**。主に除外条件、補助的 distress check。 |
| **Financial Ratios and the Probabilistic Prediction of Bankruptcy** — Ohlson, 1980, *Journal of Accounting Research* | 代表的な1年モデルの再現式: \(O=-1.32-0.407\log(TA/GNP)+6.03(TL/TA)-1.43(WC/TA)+0.0757(CL/CA)-1.72OENEG-2.37(NI/TA)-1.83(FFO/TL)+0.285INTWO-0.521CHIN\)。\(P(\text{failure})=\frac{1}{1+e^{-O}}\)。citeturn26search0turn21search5turn49view0 | 総資産、負債、運転資本、流動比率、債務超過ダミー、純利益、FFO、2年連続赤字ダミー、利益変化。 | 条件付き logit による bankruptcy prediction。QMJ の safety 定義にも O-score が組み込まれる。citeturn26search0turn27view0 | Buffett の「安全性」を、Altman より広く logit 的に測る。 | 変数は EDINET で概ね取得可能。絶対確率より cross-sectional rank で使う方が日本向け。金融には非推奨。EDINET◎ / JPX△ / yfinance△。citeturn49view0turn43search3 | **採用**。Phase1 では Altman より優先度の高い distress 除外式。 |
| **The Detection of Earnings Manipulation** — Beneish, 1999, 未公刊稿の広く流通する版 / 後に *Financial Analysts Journal* 系で広く実務普及 | 一般に用いられる 8変数式: \(M=-4.84+0.92DSRI+0.528GMI+0.404AQI+0.892SGI+0.115DEPI-0.172SGAI+4.679TATA-0.327LVGI\)。citeturn21search6 | 売掛金日数指数、粗利率悪化、資産品質、売上成長、減価償却、販管費、総 accruals、レバレッジ。変数定義は原論文が詳細に説明。citeturn42view1turn8view7 | holdout sample でも manipulators の識別に一定の有効性はあるが、著者自身が**large error rates** と further investigation の必要を強調。citeturn42view0 | Buffett 型の「会計の信頼性」には関係するが、主軸ではなく forensic control。 | 日本では会計区分や M&A の影響で誤警報が増えやすい。金融には不向き。EDINET◎ / JPX△ / yfinance△。citeturn42view0turn43search3 | **不採用**。入れても赤旗チェックの参考に留める。 |
| **Fama-French 5-factor の RMW/CMA** — Fama & French, 2015, *JFE* / Ken French Data Library | \(RMW=\frac12(Small\ Robust+Big\ Robust)-\frac12(Small\ Weak+Big\ Weak)\)。\(CMA=\frac12(Small\ Conservative+Big\ Conservative)-\frac12(Small\ Aggressive+Big\ Aggressive)\)。citeturn14view0 | OP, Inv を二次元ソート。OP と Inv の企業属性定義は Ken French library 準拠。citeturn14view3turn15view0 | 収益性・投資行動が平均リターンの説明に寄与。HML の冗長性も報告。citeturn8view9turn35view4 | Buffett の「高採算・無駄な拡張をしない」面に対応。 | 既に QMJ・GP/A・F-score と重複しやすい。金融・保険への直用は弱い。EDINET◎ / JPX△ / yfinance△。citeturn14view3turn15view0turn45view1 | **部分採用**。選定式より benchmark / robustness に向く。 |
| **Contrarian Investment, Extrapolation, and Risk** — Lakonishok, Shleifer, Vishny, 1994, *Journal of Finance* | 固有の単一式というより、B/M・CF/P・E/P・Sale Growth 等での value/growth ソート。 | 複数の value characteristics。 | value 戦略の高リターンは、典型的投資家の誤った期待形成を利用している可能性が高いと主張。citeturn7search0turn7search4 | Buffett の value leg の理論的後ろ盾。 | 実装上は B/M と E/P を採るだけで十分。個別に追加式化する必要は薄い。 | **参考採用**。理論的根拠として使い、実装は B/M・E/P に集約。 |

### 検証式または Phase2以降に回すべき式

| 論文名・著者・年・出所 | 式の正確な形 | 主要変数定義 | 何を測るか・実証結果の要約 | Buffett型投資との対応 | 日本株3,299社への注意 / 金融業適用 / データ可否 | Phase1での位置づけ |
|---|---|---|---|---|---|---|
| **Portfolio Selection** — Markowitz, 1952, *Journal of Finance* | \(E(R_p)=\sum_i w_iE(R_i)\)、\(Var(R_p)=\sum_i\sum_j w_iw_j\sigma_{ij}\)。原論文は期待値・分散・共分散から mean-variance を定式化。citeturn19view2 | weight, expected return, covariance。 | 現代ポートフォリオ理論の原点。 | Buffett 的 stock picking を補完する**配分検証**。 | 期待収益率推定が必要で、選定式にすると恣意性が入りやすい。 | **検証式のみ採用**。最終20銘柄の ex post 検証用。 |
| **The Sharpe Ratio** — Sharpe, 1994, *Journal of Portfolio Management* | \(SR=\frac{R_p-R_f}{\sigma(R_p-R_f)}\) | ポートフォリオ収益、無リスク金利、超過収益の標準偏差。citeturn29search3turn29news38 | risk-adjusted return 指標。 | Buffett proxy の「効率」を検証する。 | 投資意思決定の主式ではなく performance evaluation に使う。 | **検証式のみ採用**。 |
| **The Performance of Mutual Funds in the Period 1945–1964** — Jensen, 1968, *Journal of Finance* | \(R_{jt}-R_{ft}=a_j+b_j(R_{Mt}-R_{ft})+u_{jt}\)。\(a_j\) が Jensen’s alpha。citeturn31view0 | excess return, market excess return, beta, intercept。 | 著者は intercept が manager skill の平均増分収益率を表すと説明。citeturn31view0turn30view3 | Buffett proxy が単なる market beta でないかを確認する。 | CAPM 前提が強い。日本株では benchmark の選択に注意。 | **検証式のみ採用**。 |
| **Digesting Anomalies: An Investment Approach** — Hou, Xue, Zhang, 2015, *Review of Financial Studies* | \(E[R_i-R_f]=\beta_{MKT}E[MKT]+\beta_{ME}E[R_{ME}]+\beta_{I/A}E[R_{I/A}]+\beta_{ROE}E[R_{ROE}]\) | 市場、サイズ、投資、収益性。citeturn40search10turn40search2 | nearly 80 anomalies のうち多くを要約すると主張。citeturn40search0turn40search2 | 理論的には魅力的だが、Phase1 の Buffett proxy としては説明軸がやや広すぎる。 | FF5 と重複。学習コストの割に Phase1 の明快さを損ないやすい。 | **不採用**。必要なら Phase2 以降の robustness。 |
| **Momentum 系列** — Carhart ほか | 各種過去リターン指標 | 過去12-2か月等 | 強い実証はあるが、Buffett の守ではない。 | Buffett 的解釈が弱い。 | Phase1 の主題から外れる。 | **不採用**。 |

## 各式の詳細解説

**QMJ は、Phase1 の「完成された堀」を最も広く捉える式です。**  
QMJ の強みは、quality を単なる ROE や営業利益率に還元せず、**profitability・growth・safety・payout** の四面体で捉えることにあります。とくに safety に **O-Score、Z-Score、低レバレッジ、低 idiosyncratic volatility** を入れている点が、Buffett 的な「質は高いが無理をしていない会社」という直観に近いです。Phase1 で独自に `MOAT score` を作る代わりに、**QMJ の既製 quality score** を採ることには十分な学術的正当性があります。citeturn17view0turn19view1turn27view0

**Gross Profitability は、QMJ より単純で、なおかつ非常に強い profitability 指標です。**  
Novy-Marx の貢献は、営業段階よりもさらに上流の **gross profits / assets** が、book-to-market と並ぶほど強い cross-sectional predictor だと示したことにあります。しかもこの指標は、営業外項目や資本構成の影響を比較的受けにくく、学校プロジェクトでも説明しやすいです。Phase1 では QMJ を broad quality、GP/A を transparent profitability として並べると、**「堀の広さ」と「収益エンジンの太さ」**を分けて説明できます。citeturn16view1turn16view3turn16view4

**Value の中心は B/M と E/P の二本柱でよく、HML をその企業属性に引き戻して使うのがよいです。**  
Fama-French の HML は因子としては portfolio spread ですが、企業選別の現場では実質的に **high B/M stocks を選ぶ価値属性**です。Basu の E/P 効果は、利益に対して価格が安い企業が高い将来収益率を示したという、より直感的な Buffett 軸を与えます。2015年の FF5 では HML の冗長性が報告されましたが、これは**直接の株式選定で B/M を捨てるべき**という意味ではありません。むしろ Buffett の proxy を作るなら、**B/M と E/P を明示的に残した方が「合理的な価格」が見えやすい**です。citeturn14view0turn35view4turn34view0turn41view2

**Piotroski F-Score は、「安いだけのバリュー株」を「安くて改善している会社」に変える式です。**  
F-Score のポイントは、Value 投資を単独では使わず、**高 B/M 群の内部で財務的に強い会社を分ける**ことです。これは Buffett の「葉巻の吸い殻」を避ける実践に近いです。ROA、CFO、accruals、margin、turnover、leverage、liquidity、equity issuance という 9 つのシグナルは、日本株でも比較的再現しやすく、しかも binary sum なので説明可能性が高いです。Phase1 では、F-Score を**主 ranking ではなく、minimum quality gate**として使うと特に効きます。citeturn8view2turn12view5turn38view0

**Sloan accruals は、会計の質を一段深く見るための式です。**  
Buffett の文脈で会計の質を語るなら、単に黒字かどうかでは足りません。Sloan が示したのは、**利益のうち accrual 部分は cash flow 部分より持続性が低い**という点です。したがって、利益が出ていてもその中身が accrual に偏っている企業は、Phase1 の「守」の感覚に合いません。実務上は **低 accruals を好む**、あるいは Piotroski の **CFO > ROA** シグナルと組み合わせるだけでも十分です。citeturn10view0turn12view0turn11view1

**Distress 指標は、選ぶためよりも“落とすため”に使う方が Phase1 向きです。**  
Altman Z は歴史的に有名ですが、原式は**公開製造業**ベースです。Ohlson O は logit 型で柔軟性が高く、QMJ の safety 定義にも入っています。そのため日本株の非金融ユニバースでは、**O-score を主、Altman Z を従**とするのが妥当です。ただし日本市場に米国原標本の閾値をそのまま持ち込むのは避け、**bottom decile exclusion** のような rank-based 運用にした方が安全です。citeturn25view0turn26search0turn27view0turn49view0

**Beneish M-Score と q-factor は、「面白いが Phase1 の中核ではない」式です。**  
Beneish は manipulation detection として有名ですが、著者自身が large error rates と追加調査の必要性を認めています。したがって、これを強い除外条件にすると false positive を招きやすいです。q-factor はアセットプライシング上は強力ですが、Phase1 の目的は anomaly digesting ではなく Buffett proxy の明快な再現です。FF5 と QMJ と GP/A をすでに採るなら、q-factor まで加える必要性は低いです。citeturn42view0turn40search0turn40search2

**Markowitz, Sharpe, Jensen は選定式ではなく、仕上がりの検証器です。**  
Markowitz は portfolio variance の最小化と expected return の最大化を統一的に示した古典ですが、銘柄選定そのものの式というより、**選んだ20社の組み合わせが過度に相関していないか**を見るための器です。Sharpe ratio は risk-adjusted return、Jensen’s alpha は market beta を控除した residual performance を測ります。Phase1 では、**銘柄選択は論文由来の企業属性で行い、ポートフォリオ評価だけを Sharpe / Jensen / Markowitz で行う**のが最もきれいです。citeturn19view2turn29search3turn29news38turn31view0

## バフェット型投資との対応と日本株実装

下表は、Buffett 型投資を**公開データで再現可能な要素**に落とし、それぞれをどの式で測るかを整理したものです。

| Buffett型要素 | 再現可能な公開データ要素 | 主対応式 | 補助式 | 実装上の解釈 |
|---|---|---|---|---|
| 良い会社 | broad quality | QMJ Quality | F-Score | 収益性・安全性・配当/希薄化耐性をまとめて確認する。citeturn17view0turn19view1turn12view5 |
| 高い収益力 | profitability | Gross Profitability, RMW/OP | ROA, CFO | すでに収益が出ている堀を測る。citeturn16view1turn14view3 |
| 利益の質 | cash-flow quality / earnings quality | Sloan Accruals | Piotroski の CFO>ROA | 黒字の“中身”を見る。citeturn10view0turn12view0turn38view0 |
| 財務健全性 | financial strength | F-Score | O-Score, Z-Score | 倒れにくさと改善度を見る。citeturn8view2turn26search0turn25view0 |
| 妥当な価格 | value | B/M, E/P | HML logic | 良い会社でも高すぎれば買わない、を数式化。citeturn14view0turn34view0 |
| 無理な拡張をしない | conservative investment | CMA / Asset Growth | F-Score leverage/liquidity | ただし Phase1 では主軸より補助に留める。citeturn15view0turn14view0 |
| 資本毀損を避ける | low distress | O-Score, Altman Z | Beneish red flag | “落とすため”の式として使う。citeturn26search0turn25view0turn42view0 |

日本株実装では、**EDINET を会計の源泉データ、JPX をユニバースと業種定義、yfinance を価格系列の補助**とみなすのが最も現実的です。EDINET は金融商品取引法ベースの開示書類の電子開示システムで、有価証券報告書等を API で取得でき、XBRL により財務諸表本表が構造化されています。JPX は Listed Company Search と sector classification を提供し、EDINET と役割分担されています。JPX 英語サイトも、法定開示の XBRL は EDINET、決算短信等は Company Announcements / Listed Company Search から取得できると案内しています。citeturn46search0turn46search1turn43search3turn43search10turn47search1turn47search0

yfinance は、Yahoo! Finance の market data へ Pythonic にアクセスできるライブラリで、価格系列には便利ですが、財務諸表については**履歴が浅いことがある**うえ、2026年時点でも balance sheet / cash flow が空になる問題や、Plus 계정でも 4年超の statement history 制約に関する議論が残っています。したがって、**財務諸表は EDINET を正、価格は yfinance を補助**という扱いが妥当です。citeturn44search3turn44search5turn44search12turn44search2

日本株で特に重要なのは、**look-ahead bias を避ける時点合わせ**です。Piotroski は fiscal year-end の4か月後からリターンを測り、Fama-French の年次ソートも前年財務を用いて翌年 7月–6月に適用します。日本株でも同様に、少なくとも**開示日ベース**、開示日がなければ**決算期末 + 120日**を用いて利用可能時点をそろえるべきです。citeturn8view2turn14view2turn14view0

**金融業・保険業・銀行業の扱いは、Phase1 では原則除外が妥当です。**  
その理由は、Phase1 で採用したい主要式の多くが、**非金融事業会社**を前提にしているからです。Novy-Marx は financial firms を除外して gross profitability を検証していますし、Altman 原式は公開製造業で作られました。Piotroski も current ratio、asset turnover、gross margin を使うため、銀行や保険会社では経済的意味が変わります。したがって、JPX の業種分類で **Banks, Securities and Commodities Futures, Insurance, Other Financing Business** を特定し、Phase1 主ポートフォリオから外すのが無難です。もし金融を扱うなら、別建ての金融版スコアカードが必要です。citeturn45view1turn25view0turn47search0turn47search2

## Phase1の推奨スクリーニング設計

Phase1 の最終設計として、私は **「段階的スクリーニング + Value × Quality の二重ソート + 等金額配分 + 検証のみ Markowitz」** を推奨します。理由は、これが最も**独自重みを排しつつ、Buffett 的な解釈可能性を保てる**からです。QMJ や F-Score そのものは既成の合成式なので使えますが、最後にさらに独自 BB Score を重み付きで作る必要はありません。Instead, 先に value で土台を作り、その内部で quality・会計の質・distress を順に通す方が、研究史に沿った構成になります。citeturn18view1turn37view0turn41view2

推奨する手順は次の通りです。  
第一に、**ユニバース定義**として、JPX 上場普通株から金融・保険・銀行・証券を除外し、極端な流動性不足や継続企業注記、必要データ欠損の大きい銘柄を落とします。第二に、**Value 一次選別**として B/M 上位群と positive E/P 高位群を取ります。第三に、**Quality 二次選別**として QMJ Quality が中央値以上、かつ Gross Profitability が中央値以上の銘柄に絞ります。第四に、**Financial Strength / Earnings Quality** として F-Score を 6 以上、Sloan accruals を悪化側から除外します。第五に、**Low Distress 除外**として O-score の worst decile と Altman Z の極端低位群を落とします。第六に、残った銘柄群に対して **Quality × Value の二重ソート**を行い、**高 Quality × 高 Value** セルから20社を採用し、**等金額配分**します。第七に、仕上がった20社ポートフォリオを Sharpe, Jensen alpha, mean-variance 上で検証します。citeturn14view0turn14view1turn16view1turn8view2turn10view0turn26search0turn25view0turn19view2turn31view0

この設計で重要なのは、**同じ情報を二重三重に重ねすぎない**ことです。たとえば RMW、Gross Profitability、QMJ Profitability は強く重なります。したがって Phase1 では、**実装式**としては QMJ + GP/A + B/M + E/P + F-Score + Accruals + O-score / Z-score に絞り、RMW/CMA は**なぜこの設計が学術的に妥当かを説明する参照軸**として使うのが妥当です。citeturn14view0turn16view1turn17view0

独自重みを避ける代替手法の比較は、以下のとおりです。

| 方法 | 長所 | 短所 | Phase1評価 |
|---|---|---|---|
| 段階的スクリーニング | 透明で説明しやすい。条件が論文由来なら恣意性が小さい。 | 閾値の決め方に裁量が残る。 | **最有力**。Phase1 の本文向き。 |
| 分位ソート | Fama-French や Sloan 研究と整合的。研究再現性が高い。 | 個別最終銘柄の tie-break が必要。 | **有力**。中核に採用。 |
| Quality × Value の二重ソート | Buffett の「良い会社を合理的価格で買う」を最も直接に表現できる。 | 銘柄数が少ないセルでは偏りが出る。 | **最有力**。最終選定の中心に採用。 |
| F-Score / Altman / Ohlson による除外 | 「買う理由」と「落とす理由」を分離できる。 | 絶対閾値の市場横断適用には慎重さが必要。 | **採用**。とくに除外条件として有効。 |
| 等金額配分 | 重み推定が不要。独自最適化を避けられる。 | リスク parity ではない。 | **採用**。Phase1 では最も無難。 |
| Markowitz による最適化 | 分散を明示的に扱える。 | 期待収益率・共分散推定に依存し、選定式に変質しやすい。 | **検証のみ**。採用しない。 |

最終的な採否は、次のように整理するのが最も明快です。  
**採用**: QMJ Quality、Gross Profitability、B/M、E/P、Piotroski F-Score、Sloan Accruals、Ohlson O-Score、Altman Z-Score、Sharpe / Jensen / Markowitz（ただし validation only）。  
**部分採用**: Fama-French HML・RMW・CMA は、企業属性と benchmark として使うが、最終 ranking をこれだけで組まない。  
**不採用または Phase2 以降**: Momentum、Future Moat keyword score、Transformation Moat Score、独自 MOAT Score、独自 BB Score、AI 関連テキスト score、q-factor の主運用、Beneish の強制除外。citeturn41view2turn16view1turn8view2turn10view0turn26search0turn25view0turn40search2turn42view0

## レポート本文案とCodexプロンプト

レポート本文にそのまま使いやすい文章案を、以下のようにまとめます。

**本文案その一**  
本研究の Phase1 では、独自の重み付き合成式を用いず、先行研究で既に定義された式とスクリーニング規則だけで Buffett 型投資を再構成する。独自式は一見わかりやすい反面、係数の根拠が研究史に基づかず、再現可能性と説明責任が弱くなりやすい。これに対し、Quality Minus Junk、Gross Profitability、Fama-French の属性ソート、Piotroski F-Score、Sloan Accruals は、いずれも査読研究や広く引用される実証研究で定義された指標であり、式そのものに学術的な由来がある。したがって Phase1 は、自分たちの好みで係数を置くのではなく、文献で定義済みの指標を組み合わせることで、研究としての再現性を優先する。citeturn18view1turn16view1turn37view0turn14view0

**本文案その二**  
Phase1 が目指すのは、Buffett の投資のすべてを再現することではない。Frazzini, Kabiller, Pedersen が示すように、Buffett の成果の大きな部分は、割安で、安全で、高品質な株式への長期投資によって説明できる。しかし、保険フロートによる低コストレバレッジ、非公開企業買収、経営者との対話、交渉力、税の繰延べといった要素は、公開データだけでは再現できない。そこで Phase1 では、公開財務データで観測可能な Value、Quality、Profitability、Cash Flow Quality、Financial Strength、Low Distress のみを対象にし、Buffett Proxy Portfolio を構築する。citeturn41view1turn41view2turn41view3

**本文案その三**  
この意味で、Phase1 は守・破・離の「守」に当たる。ここで扱うのは、AI 時代の将来競争優位や、資本効率改革による企業変容の予兆ではなく、すでに財務諸表や市場価格に表れている“完成された堀”である。高い gross profitability、低い accruals、改善した財務体質、低い distress risk、そして book-to-market や earnings yield に表れる合理的な価格は、将来像ではなく現在観測できる企業の質を表している。Phase2 以降では、Future Moat や Transformation Moat のような変化の源泉を追加するが、Phase1 ではまず Buffett 型投資の土台を、公開データだけで再現できる範囲に限定する。citeturn16view1turn10view0turn8view2turn26search0

**本文案その四**  
最終的に本研究は、将来リターンを保証するモデルを作ることを目的としない。むしろ、査読研究で広く検証されてきた式を用いて、Buffett 的な投資原則のうち公開情報で追跡できる部分を、できるだけ恣意性なく定量化することを目的とする。そのため最終ポートフォリオは、独自スコアの上位銘柄ではなく、Value と Quality の二重ソート、F-Score や distress 指標による除外、そして等金額配分という、先行研究の延長上にある構造で構成する。citeturn14view0turn37view0turn19view2turn31view0

以下は、**データ取得済みの日本株 3,299 社データをローカル環境で Codex に処理させるための、そのまま使えるプロンプト案**です。

```text
あなたは、金融経済学・会計ファイナンス・クオンツ投資に精通した実装担当者です。
目的は、日本株3,299社の既取得データだけを使って、日経STOCKリーグ向け「BEYOND BUFFETT」Phase1（守）の
Buffett Proxy Portfolio を構築することです。

重要制約:
- インターネット検索は禁止。ローカルにある既取得データだけを使うこと。
- 独自の重み付き合成式は禁止。
- AI関連、Future Moat、Transformation Moat、政策保有株削減、中計テキスト分析は禁止。
- 金融業・保険業・銀行業・証券を主ポートフォリオ母集団から除外すること。
- 選定は論文由来の式・binary score・portfolio sort・sequential screen だけで行うこと。
- 最終ポートフォリオは20銘柄、等金額配分にすること。
- Markowitz最適化で銘柄やウェイトを決めてはいけない。Markowitzは検証のみ。

利用する式:
1) B/M = Book Equity / Market Equity
2) E/P = trailing earnings / price
3) Gross Profitability = (Revenue - COGS) / Total Assets
4) Sloan Accruals
   - 可能なら: (Net Income before extraordinary items - CFO) / Avg Total Assets
   - CFOがない場合のみ、Sloan(1996)のバランスシート近似:
     ((ΔCA - ΔCash) - (ΔCL - ΔSTD - ΔTP) - Dep) / Avg Total Assets
5) Piotroski F-Score = 9 binary signals
   - FROA: ROA > 0
   - FCFO: CFO > 0
   - FΔROA: current ROA > prior ROA
   - F_ACCRUAL: CFO > ROA
   - FΔMARGIN: current gross margin > prior gross margin
   - FΔTURN: current asset turnover > prior asset turnover
   - FΔLEVER: leverage ratio < prior leverage ratio
   - FΔLIQUID: current ratio > prior current ratio
   - EQ_OFFER: no common equity issuance in prior year
6) Ohlson O-Score
   O = -1.32 - 0.407*log(TA/GNP_proxy) + 6.03*(TL/TA) - 1.43*(WC/TA)
       + 0.0757*(CL/CA) - 1.72*OENEG - 2.37*(NI/TA) - 1.83*(FFO/TL)
       + 0.285*INTWO - 0.521*CHIN
   - GNP deflatorがなければ cross-sectional rank用途なので、log(TA) proxy を使う前に必ず
     「原式からの逸脱」としてレポートすること。勝手に置き換えたらダメ。
   - もし必要変数が欠けるなら O-Score は計算不能として扱い、Altman Z のみ補助利用すること。
7) Altman Z-Score
   - 製造業型原式: Z = 1.2*WC/TA + 1.4*RE/TA + 3.3*EBIT/TA + 0.6*MVE/TL + 1.0*Sales/TA
   - 非製造・日本市場での閾値の直用は避け、cross-sectional rank / bottom-tail exclusion としてのみ用いること。
8) QMJ Quality
   - 必要変数が揃う場合のみ実装。
   - rank を z-score 化して、論文定義どおり profitability / growth / safety / payout を構成し、
     その平均から overall quality を作ること。
   - 必要変数が不足する場合は、勝手に独自簡略化しない。代わりに
     「QMJ full unavailable」と明示し、Gross Profitability + F-Score + Accruals + Distress で代替すること。

データ処理ルール:
- 普通株のみ対象。ETF, REIT, preferred, foreign share class は除外。
- セクター除外は JPX 33業種または取得済み業種分類で、
  Bank, Insurance, Securities/Commodity Futures, Other Financing を除外。
- 会計データは look-ahead bias を避けること。
  優先順位:
  (a) filing_date / disclosure_date がある場合はその日以降にのみ利用
  (b) なければ fiscal_year_end + 120日ルール
- 欠損補完は最小限。勝手な推定や業界平均代入は禁止。
- 極端値は winsorize してよいが、その場合は上下何%かを明記すること。
- 負のBook Equity銘柄は B/M から除外。
- 赤字企業は E/P から除外。ただし他の式には残してよい。

スクリーニング手順:
Step 1: Universe
- 非金融の普通株ユニバースを作成。
- 必須項目欠損銘柄数を集計し、除外理由別にカウントする。

Step 2: Value screen
- B/M を計算し、上位30%を通過。
- E/P を計算し、正のE/P銘柄のうち上位50%を通過。
- 上の両方を満たす銘柄を残す。

Step 3: Quality screen
- Gross Profitability を計算し、ユニバース中央値以上を通過。
- QMJ full が計算可能なら overall quality が中央値以上を通過。
- QMJ full が計算不能なら、その旨を出力し、代替として
  Gross Profitability と F-Score を主 quality proxy とする。

Step 4: Financial strength / earnings quality screen
- F-Score >= 6 を通過条件とする。
- Sloan Accruals は「低いほど良い」とし、悪い側上位30%を除外。
- CFO > ROA シグナルも報告する。

Step 5: Distress exclusion
- O-Score が計算可能なら、悪い側上位10%を除外。
- Altman Z は低い側下位10%を除外。
- O-Score と Altman Z の両方がある場合は、どちらか一方でも極端に悪い銘柄を除外。

Step 6: Final selection by double sort
- 残存銘柄に対し、Value と Quality の二重ソートを実施。
- Value は B/M と E/P の平均順位ではなく、
  まず B/M tercile、次にその内部で E/P tercile を確認し、
  最終的に「high value」群を定義すること。
- Quality は QMJ full がある場合は QMJ tercile、
  ない場合は Gross Profitability tercile を主軸に、F-Score を補助に使う。
- 最終的に High Value × High Quality セルから候補を抽出。

Step 7: Final 20 names
- 候補が20超なら、以下の順で sequential tie-break を行う:
  1. higher F-Score
  2. lower Sloan Accruals
  3. higher Gross Profitability
  4. lower O-Score
  5. higher Altman Z
- それでも同順位なら時価総額が大きい順で20銘柄にする。
- ウェイトは全銘柄 5% の等金額配分。

検証:
- 月次リターンがある場合、最終20銘柄 equal-weight portfolio の
  年率リターン、年率ボラ、Sharpe Ratio を計算。
- ベンチマークに対する CAPM 回帰で Jensen alpha を計算。
- 共分散行列を使って ex post portfolio variance を計算し、
  equal-weight と minimum-variance（参考のみ）を比較する。
- ただし最終採用ウェイトは equal-weight のままに固定。

出力物:
1. 各ステップの銘柄数推移
2. 各指標の計算式一覧
3. 欠損処理・winsorize・look-ahead回避ルール
4. 最終20銘柄一覧
5. 各銘柄の B/M, E/P, GP/A, F-Score, Accruals, O-Score, Z-Score, sector, market cap
6. 除外銘柄の理由一覧
7. 検証結果（Sharpe, Jensen alpha, portfolio variance）
8. 再現可能な Python スクリプト一式
9. CSV 出力:
   - phase1_universe.csv
   - phase1_metrics.csv
   - phase1_candidates.csv
   - phase1_final20.csv
10. README:
   - どの論文由来式をどう実装したか
   - どの式を採用し、どの式を補助・除外に回したか
   - どの変数が不足していて、どこで原式に忠実に実装できなかったか

最重要事項:
- 勝手な独自スコアを作らない。
- 重み付き総合点を作らない。
- 原式が使えないときは「使えない」と報告し、代替した場合は必ず明示する。
- 途中経過を可視化し、監査可能な実装にする。
```

## 参考文献一覧

Asness, Clifford S., Andrea Frazzini, and Lasse Heje Pedersen. “Quality Minus Junk.” *Review of Accounting Studies* 24, no. 1, 2019. 定義は AQR working paper 版 appendix でも確認できる。citeturn17view0turn19view1

Altman, Edward I. “Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy.” *Journal of Finance* 23, no. 4, 1968.citeturn25view0

Basu, Sanjoy. “Earnings’ Yield and the Size Effect.” *Journal of Financial Economics* 12, no. 1, 1983. 関連原論文として 1977年 *Journal of Finance* 論文も重要。citeturn34view0

Beneish, Messod D. “The Detection of Earnings Manipulation.” 1999年版テキストが広く流通。citeturn8view7turn42view1turn42view0

Fama, Eugene F., and Kenneth R. French. “Common Risk Factors in the Returns on Stocks and Bonds.” *Journal of Financial Economics* 33, 1993. 因子定義の実務実装は Ken French Data Library で継続公開。citeturn14view1turn13view0

Fama, Eugene F., and Kenneth R. French. “A Five-Factor Asset Pricing Model.” *Journal of Financial Economics* 116, no. 1, 2015.citeturn8view9turn35view4

Frazzini, Andrea, David Kabiller, and Lasse H. Pedersen. “Buffett’s Alpha.” *Financial Analysts Journal* 74, no. 4, 2018. Working paper 版も有用。citeturn41view1turn41view2turn41view3

Hou, Kewei, Chen Xue, and Lu Zhang. “Digesting Anomalies: An Investment Approach.” *Review of Financial Studies* 28, no. 3, 2015.citeturn40search2turn40search13

Jensen, Michael C. “The Performance of Mutual Funds in the Period 1945–1964.” *Journal of Finance* 23, no. 2, 1968. この式が Jensen’s alpha の標準形。citeturn31view0

Ken French Data Library. Fama/French 3 factors, 5 factors, size-B/M, size-OP, size-Investment の定義と国別ポートフォリオ。citeturn14view0turn14view1turn14view2turn14view3turn15view0turn13view0

Lakonishok, Josef, Andrei Shleifer, and Robert W. Vishny. “Contrarian Investment, Extrapolation, and Risk.” *Journal of Finance* 49, no. 5, 1994.citeturn7search4turn7search0

Markowitz, Harry. “Portfolio Selection.” *Journal of Finance* 7, no. 1, 1952.citeturn19view2

Novy-Marx, Robert. “The Other Side of Value: The Gross Profitability Premium.” *Journal of Financial Economics* 108, no. 1, 2013.citeturn16view1turn16view4

Ohlson, James A. “Financial Ratios and the Probabilistic Prediction of Bankruptcy.” *Journal of Accounting Research* 18, no. 1, 1980. 代表式の整理には後年のレビューも参照。citeturn26search0turn49view0turn21search5

Piotroski, Joseph D. “Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers.” *Journal of Accounting Research* 38, Supplement, 2000.citeturn8view2turn12view5turn38view0

Sharpe, William F. “The Sharpe Ratio.” *Journal of Portfolio Management* 21, no. 1, 1994. オンライン版・解説参照。citeturn29search3turn29news38

Sloan, Richard G. “Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?” *The Accounting Review* 71, no. 3, 1996.citeturn10view0turn12view0turn11view1

EDINET（金融庁） API・開示システム説明。citeturn46search0turn46search1

Japan Exchange Group. Listed Company Search, sector classification, disclosure gate.citeturn47search1turn47search0turn43search10

yfinance 公式ドキュメント・リポジトリ。価格系列には有用だが、財務諸表取得は補助扱いが妥当。citeturn44search3turn44search0turn44search5turn44search2