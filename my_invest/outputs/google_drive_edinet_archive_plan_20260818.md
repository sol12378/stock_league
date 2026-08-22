# EDINET全原本をGoogle Drive 5TBへ格納する実行計画

策定日: 2026-08-18 JST

## 1. 結論

Google Drive 5TBは、本調査のEDINET全原本、派生テーブル、学習データを収容できる。EDINET原本の推定総容量は約614〜743 GiB（約660〜798 GB）である。

ただし、約140万ファイルをGoogle Driveへ個別アップロードしない。原本ファイルのバイト列とパスを保持したまま、10〜20 GiBの不変tarシャードへまとめてアップロードする。これにより、Drive上のアイテム数、API呼出し数、再同期時間、重複事故を大幅に減らす。

Google Drive for desktopの同期フォルダへEDINET取得先を直接向けない。Drive APIへrcloneで明示的にアップロードし、ハッシュ検証完了後だけローカルのステージングデータを解放する。

## 2. 前提と制約

### Google Drive側

- 1ユーザーのアップロード・コピーは24時間で750 GBまで。
- 1ファイルの最大アップロードサイズは5 TB。
- 共有ドライブは50万アイテム上限があるため、140万原本を個別配置できない。
- Drive APIは429/403を返し得るため、指数バックオフと再開が必要。
- Google Driveは通常ファイルのMD5、SHA-1、SHA-256を扱えるが、最終監査ではローカルSHA-256台帳を正とする。

公式資料:

- https://developers.google.com/workspace/drive/api/guides/limits
- https://support.google.com/a/users/answer/7338880
- https://rclone.org/drive/

### 現在のEDINET台帳

- 期間: 2016-08-18〜2026-08-18、3,653日
- 正味書類: 888,871件
- 取得対象payload: 1,409,727件
- 取得済みpayload: 11,704件
- 公式公開資産: 810件取得済み、公式側404が1件
- 現在のローカルアーカイブ: 約14 GB
- 推定完成原本: 約614〜743 GiB

## 3. 5TBの割当

| 領域 | 上限目安 | 用途 |
|---|---:|---|
| Bronze | 1.0 TB | EDINET原本シャード、日次JSON、公式仕様、コード表、タクソノミ |
| Silver | 1.2 TB | 展開XBRL、全ファクト、文章、所有・資本・監査イベント |
| Gold | 0.5 TB | point-in-time特徴量、ラベル、学習・テストスナップショット |
| Experiments | 0.5 TB | モデル、予測、説明、評価結果 |
| Snapshots | 0.8 TB | manifest世代保存、重要派生物のチェックポイント |
| Free reserve | 1.0 TB | 将来開示、再計算、一時世代、容量誤差 |

原本領域が1TBを超えた場合は、SnapshotsとFree reserveから振り替える。常時15〜20%を空ける。

## 4. Drive上の構成

```text
EDINET_2X_RESEARCH/
  00_control/
    README.md
    archive_catalog.json
    manifests/
    checksums/
    acquisition_logs/
  10_bronze/
    daily_lists/
    public_assets/
    payload_shards/
      type1/YYYY/MM/
      type2/YYYY/MM/
      type3/YYYY/MM/
      type4/YYYY/MM/
      type5/YYYY/MM/
  20_silver/
  30_gold/
  40_models/
  50_reports/
  90_snapshots/
```

シャード名は内容から一意に決める。

```text
edinet_type1_2025_06_part0001_<sha256先頭12桁>.tar
```

同名を上書きせず、既存ファイルのハッシュが違う場合は停止する。

## 5. シャード仕様

### 単位

- 基本キー: `payload_type / submit_year / submit_month`
- 目標サイズ: 10〜20 GiB
- 最大サイズ: 25 GiB
- 1シャード内の最大ファイル数: 25,000件
- 圧縮: 原則なしのtar。ZIP/PDFは既に圧縮済みで、再圧縮の効果が小さいため。
- 日次JSONやmanifest exportだけはzstd圧縮を許可する。

### 各シャードに必要な管理情報

- `shard_sha256`
- `shard_md5`（Drive照合用）
- バイト数
- 内包ファイル数
- 各原本の相対パス、docID、API type、byte_size、SHA-256
- 提出日時範囲
- 作成日時と作成プログラムのGit commit
- tar一覧のSHA-256

tar化は原本の内容を変更しない。復元後の各ファイルSHA-256がEDINET取得時の台帳と一致することを完了条件とする。

## 6. 転送方式

### 推奨ツール

rcloneをGoogle Drive APIへOAuth接続する。Google Drive for desktopの同期領域は閲覧用に留め、数百GBの取得・退避パイプラインには使わない。

OAuth権限は、可能ならrcloneが作成したファイルだけを扱う`drive.file`を使う。既存Drive全体の読み書きが必要な場合だけ`drive`権限へ拡張する。rclone設定ファイルとOAuthトークンはローカル秘密情報として扱い、Drive、Git、ログへ入れない。

### 重要な運用ルール

- `sync`は使用しない。ローカルを解放した後に実行するとDrive側を削除し得る。
- `copy`又は`copyto`だけを使用する。
- `--immutable`で既存オブジェクトの変更を拒否する。
- `--checksum`で内容照合する。
- `--drive-stop-on-upload-limit`で750 GB制限時に停止する。
- 転送後に`rclone checksum`又は`rclone check`を実行する。
- Drive側検証前にローカル原本を削除しない。
- 失敗時は同じシャードを再開し、別名コピーを作らない。

実装時のコマンド骨格:

```bash
rclone copyto LOCAL_SHARD gdrive:EDINET_2X_RESEARCH/10_bronze/payload_shards/REMOTE_SHARD \
  --immutable --checksum --drive-stop-on-upload-limit \
  --transfers 2 --checkers 4 --retries 10 --low-level-retries 20

rclone checksum md5 LOCAL_MD5SUM gdrive:EDINET_2X_RESEARCH/10_bronze/payload_shards/PATH \
  --one-way
```

実コマンドには秘密値を含めない。

## 7. EDINET取得からDrive格納までの状態機械

1. `planned`: EDINET一覧からpayload取得対象を登録
2. `downloaded`: ローカルステージへ原本取得、形式・SHA-256検証済み
3. `packed`: 不変tarシャード完成、内包manifest確定
4. `uploaded`: Driveへの転送終了
5. `remote_verified`: Driveのサイズ・MD5とローカルが一致
6. `sample_restored`: 抽出復元標本の個別SHA-256が一致
7. `released`: ローカルの個別原本とシャードを安全に解放

`remote_verified`より前のローカル削除は禁止する。SQLiteにはローカル状態とDrive file ID、remote path、remote hash、検証時刻を記録する。

## 8. 取得順序

研究価値と容量効率を考慮して順序だけを最適化し、全typeを最終取得対象に残す。

1. 日次一覧、コード表、API仕様、タクソノミ
2. type 4（残件が少ない）
3. type 5（CSV変換、財務モデルへ直結）
4. type 1（XBRL本文、文章、監査情報）
5. type 3（添付・代替書面）
6. type 2（PDF原本）

各typeを月単位で取得し、シャード検証・Drive退避・ローカル解放まで終えてから次月へ進む。これによりローカル使用量を40〜80 GiB程度に抑える。

## 9. 実行フェーズ

### Phase 0: 認証と書込み試験

- rcloneを導入
- 専用OAuthクライアントを作成又はrclone標準OAuthで認証
- `rclone about`で5TB割当と残容量を確認
- 専用ルートフォルダを作成
- 1 MiB、1 GiBの試験ファイルをupload→hash check→download→hash check
- 試験ファイルを削除する場合はユーザー確認後に行う

### Phase 1: 管理情報の複製

- 日次一覧JSON
- 公式公開資産
- SQLiteのオンラインコピー
- SQLiteからCSV/Parquetへ出した可搬manifest
- 取得プログラム、README、容量計画、2倍株計画

SQLite稼働ファイルを同期フォルダ上で直接更新しない。ローカルで`VACUUM INTO`又はbackup APIにより一貫したスナップショットを作ってからアップロードする。

### Phase 2: 取得済み原本のシャード化・移送

- 現在の約14 GBを月・type別シャードへ変換
- Drive検証後も、最初の完全復元試験が終わるまでローカル原本を維持
- ランダム100件と最大サイズ上位20件を復元しSHA-256照合

### Phase 3: 残り全原本のストリーミング取得

- 月単位でEDINETから取得
- 10〜20 GiBごとにシャード確定
- Driveへcopyto
- remote hash検証
- manifestをDriveへ追記スナップショット
- ローカルを解放

EDINETへのアクセス間隔を維持する。約140万リクエストのため、アップロード容量よりEDINET取得時間が支配的になる。中断・再開を前提とし、7〜14日程度の連続運転枠を確保する。

### Phase 4: 完全性監査

- 全payload行が`remote_verified`又はAPI明示の`unavailable`
- Drive上の全シャード件数・容量・MD5一致
- 全シャードmanifestのSHA-256一致
- type・年・月ごとの対象件数と内包件数一致
- 1%無作為復元と全大容量ファイル復元を個別SHA-256照合
- 欠損、API 404、取得エラー、再試行回数を独立レポート化

### Phase 5: 2倍株研究データ

- Bronze原本をDriveから必要月だけローカルキャッシュへ取得
- SilverはParquetを年・concept群単位で作成
- Goldはanchor date単位で固定し、2025-06特徴量と2026-06評価を混在させない
- 学習スナップショットにもSHA-256と原本docID系譜を付ける

## 10. 日次上限と所要時間

原本完成容量が最大推計の約800 GB（10進）に達すると、Googleの750 GB/24時間制限を1日で超える可能性がある。1日500 GBを自主上限として2日以上へ分割する。ただしEDINET取得が律速になるため、実際には日次上限へ達しない可能性が高い。

アップロードだけの理論時間:

| 実効上り速度 | 660 GB | 800 GB |
|---:|---:|---:|
| 50 Mbps | 約29時間 | 約36時間 |
| 100 Mbps | 約15時間 | 約18時間 |
| 300 Mbps | 約5時間 | 約6時間 |

実運用ではAPI応答、tar作成、再試行、検証を含め、この表より長い。

## 11. セキュリティと削除防止

- EDINET APIキー、Google OAuth token、rclone設定はアップロードしない。
- `.env`、`rclone.conf`、ログ中のAuthorization headerを明示除外する。
- Driveルートは専用フォルダとし、他データを処理対象にしない。
- 取得・アップロード工程に削除権限を持たせない又は削除処理を実装しない。
- ローカル解放は別コマンドに分離し、`remote_verified`のみを対象にする。
- Driveのゴミ箱を自動で空にしない。
- manifestは日次世代保存し、少なくとも直近30世代を保持する。

## 12. 完了基準

次をすべて満たした時点で「Google Driveへの全原本格納完了」とする。

1. 3,653日分の日次一覧原本がDrive上にある。
2. 公式公開資産810件があり、公式404の1件が欠損台帳にある。
3. 1,409,727 payload行が`remote_verified`又は`unavailable`等の説明可能な終端状態である。
4. Drive上のシャードとローカルmanifestの件数・容量・ハッシュが一致する。
5. 無作為復元監査と大容量ファイル監査に不一致がない。
6. APIキー及びGoogle認証情報がDrive・Git・ログに存在しない。
7. 完了監査JSON、Markdown、可搬CSV/Parquet manifestがDriveとローカル双方にある。

## 13. 実装前にユーザーが行う操作

実装・転送開始時に必要なのは、ブラウザでGoogleアカウントへのOAuth許可を1回行うことだけである。認証後は、取得・シャード化・アップロード・検証を自動再開できる。アップロード先は既存ファイルと混ざらない専用フォルダを使用する。
