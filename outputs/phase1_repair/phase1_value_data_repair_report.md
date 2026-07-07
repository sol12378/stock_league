# Phase1 Value Data Repair Report

## 1. 前回Phase1でB/M・E/Pが少なかった理由
yfinance由来の `market_cap`、PBR、PER が約300社に限られ、非金融ユニバース全体の market equity を再構成できていませんでした。

## 2. B/M・E/Pの理論式
- B/M = Book Equity / Market Equity
- E/P = Earnings / Market Equity

## 3. 今回取得・再構成したデータ
EDINET XBRLから発行済株式数と自己株式数を抽出し、既存株価 `close` と結合しました。

## 4. market_equityの再構成方法
優先順位は raw market_cap、close × EDINET shares outstanding、book equity × raw PBR、net income × raw PER です。

## 5. B/M・E/Pのカバレッジ改善結果
B/M・E/P両方利用可能カバレッジは 86.5% です。

## 6. 修正版Phase1のスクリーニング結果
詳細は `phase1_revised_screening_funnel.csv` を参照してください。

## 7. 最終20社の採用理由
B/M上位30%、E/P上位50%、Piotroski available signal score、Sloan accrualsで選定しました。

## 8. なお残る限界
Piotroskiは6シグナル版であり、Gross Profitability、QMJ full、Ohlson原式、Altman原式は未実装です。