
# Report Text For Paper

Phase2では、Phase1で用いた先行研究式の定義は変更せず、式の適用方法を最適化した。具体的には、B/M、E/P、Gross Profitability、Piotroski available signal ratio、Sloan Accruals、Distress、Liquidityを百分位順位などに正規化し、重み、欠損処理、業種調整、候補数を探索した。これは銘柄をAIに直接選ばせるものではなく、Phase3へ渡す候補宇宙を作るための条件比較である。

utility最大化ではTop2000が最良であったが、Phase2の目的は候補数最大化ではない。Phase3で実際に分析可能な広さ、品質、財務安全性、流動性、業種分散、レビュー負荷を考慮し、Top1200をPhase2 optimized candidate universeとして採用した。

また、正規化方式による揺れを確認するため、market percentile、sector percentile、robust z-score、winsorized z-scoreを比較し、複数方式で共通して上位に残る企業にnormalization core / robust flagを付与した。

さらに、EDINET提出日を基準にしたpoint-in-time panelを構築し、固定重みを年度別snapshotに適用することで、単一時点だけでなく時点外での候補群品質も確認した。ただし、十分なfoldを用いた完全なWalk-forward optimizationは今後の課題であり、本結果は将来リターン予測力を示すものではない。
