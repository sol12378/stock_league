# Value Coverage Audit

## 前回実装でB/M・E/Pが少なかった理由

前回は `market_cap` / raw PBR / raw PER が yfinance由来の約300社に限られ、非金融ユニバース全体へ market equity を再構成できていなかったためです。

## 今回の補完方法

EDINET XBRLから発行済株式数と自己株式数を抽出し、`Market Equity = Close Price × Shares Outstanding` を主経路として再構成しました。
`pbr_for_score` と `pe_for_score` は raw 値と証明しない限り使わない、という方針に従い、B/M・E/P補完には使っていません。

## 補完後のカバレッジ

- Phase1非金融ユニバース: 3,169社
- B/M利用可能: 3,089社 (97.5%)
- E/P利用可能: 2,750社 (86.8%)
- B/M・E/P両方利用可能: 2,740社 (86.5%)

## まだ足りないデータ

赤字企業では E/P を欠損扱いにするため、B/MよりE/Pのカバレッジが低くなります。また、EDINET株式数タグを取得できない企業では market equity が欠損します。

## データソースの信頼性

財務データは既存のEDINET抽出値、株式数はEDINET XBRL、株価は既存の価格データを使用しました。yfinance market_capは存在する場合の照合・優先値として保持しています。

## 判定

Phase1再構築へ進む