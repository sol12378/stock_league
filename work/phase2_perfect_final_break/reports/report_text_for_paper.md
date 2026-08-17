
# Report Text For Paper

Phase2では、Phase1で採用した先行研究式の定義は変更せず、式の使い方を最適化した。具体的には、B/M、E/P、Gross Profitability、Piotroski available signal ratio、Sloan Accruals、Distress、Liquidityを正規化し、重み、候補数、業種調整、欠損処理を比較した。これは銘柄をAIに直接選ばせるものではなく、Phase3へ渡す候補宇宙を作るための条件比較である。

utilityを最大化するとTop2000が最良となったが、Phase2の目的は候補数の最大化ではない。Phase3で分析可能な広さ、品質、財務安全性、流動性、業種分散、レビュー負荷を考慮し、Top1200をPhase2 optimized candidate universeとして正式採用した。

また、正規化方式による揺れに対応するため、market percentile、sector percentile、robust z-score、winsorized z-scoreを比較し、複数方式で共通して上位に残る企業にnormalization core / robust flagを付与した。

さらに、EDINET提出日を基準としたpoint-in-time panelを構築し、固定重みを年度別snapshotに適用することで、候補群の時点外確認を行った。ただし、十分なfoldを用いたtrue walk-forward optimizationは今後の課題であり、本成果物は将来リターン予測力を主張するものではない。
