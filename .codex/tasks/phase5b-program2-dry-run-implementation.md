# Phase 5B: Program2 --dry-run 最小実装タスク

## 目的

Program2 本番投入の前段として、Program2 TSV を SEALIB DB に read-only で照合し、行ごとに `ready_to_insert` / `warning` / `ambiguous` / `unmatched` / `invalid` へ分類する `--dry-run` を実装する。

Phase 5B では dry-run のみを実装する。DB 書き込みモード、DELETE / INSERT、backup、transaction、本番データ投入は実装しない。

## 前提として確認済みの設計

- `docs/program2-dry-run-design.md`
  - dry-run は `03-2-import-metrics.php` の read-only モードとして設計する。
  - INSERT 予定行は生成するが DB へは書き込まない。
- `docs/validation-layering.md`
  - `validate-tsv` は TSV の構造・書式検証を担当する。
  - Program2 `--dry-run` は SEALIB DB との header 解決・整合性検証を担当する。
  - Phase 5B では `validate-tsv` の厳密検証を重複実装しない。
- `docs/program2-resolution-strategy.md`
  - (B) 名前再解決方式を採用する。
  - `ref_id` / `ref_name` は TSV から受け取らず、投入時点の `header` から Program2 が解決する。
- `docs/convert-sheet-redesign.md`
  - Program2 TSV は以下8列:
    `metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note`
- `docs/sealib-api-oai-compatibility-audit.md`
  - `journal_metrics` の API 公開項目は `source/country/grade/url/note/imported_at`。
  - `ref_id` / `ref_name` は非公開だが、metrics 結合・絞り込みのために現行 `header` と整合している必要がある。
  - OAI-PMH は `journal_metrics` を参照しない。
- `../../sealib/docs/journal-metrics-semi-auto-design.md`
  - Program2 は SEALIB 側 `admin/import-data-ext/03-2-import-metrics.php` として設計されている。
  - `03-1-import-metrics-sinta.php` は SINTA 専用の現行実装であり、`03-2` は汎用版として新設する。
- `../../sealib/seas-3.3.1/admin/import-data-ext/03-1-import-metrics-sinta.php`
  - TSV ヘッダ名ベース判定、BOM 除去、列数不足時のパディング、PDO prepared statement が参考になる。
  - 現行 `03-1` は `sqlite:` 通常接続で DELETE / INSERT を行うため、Phase 5B の dry-run では read-only 接続へ置き換える。
- `../../sealib/seas-3.3.1/admin/import-data-ext/01-3-create-metrics-table.php`
  - `journal_metrics` スキーマ:
    `mid, ref_id, ref_name, metric_source, metric_country, grade, url, note, imported_at`

## 実装対象

候補:

```text
../../sealib/seas-3.3.1/admin/import-data-ext/03-2-import-metrics.php
```

新規 PHP CLI として追加する。既存 `03-1-import-metrics-sinta.php` は変更しない。

## CLI 仕様

必須:

```bash
php 03-2-import-metrics.php --dry-run --input /path/to/metrics.tsv --db ext
php 03-2-import-metrics.php --dry-run --input /path/to/metrics.tsv --db core
```

任意:

```bash
php 03-2-import-metrics.php --dry-run --input /path/to/metrics.tsv --db ext --report /tmp/program2-dryrun-report.tsv
```

### 引数

- `--dry-run`
  - 必須。
  - Phase 5B では dry-run のみ実装する。
  - 指定がない場合はエラー終了する。
- `--input`
  - 必須。
  - Program2 TSV のパス。
- `--db`
  - 必須。
  - `ext` または `core` のみ許可する。
  - `ext` は `SQLITE_DATA_PATH_EXT`、`core` は `SQLITE_DATA_PATH` を使う。
- `--report`
  - 任意。
  - 行ごとの分類結果を TSV で出力する。

## read-only 境界

- SQLite DB は read-only で開く。
- PDO SQLite では URI filename を使い、`mode=ro` を指定する。
- dry-run では SQL は `SELECT` のみ許可する。
- 以下は実装しない:
  - `DELETE`
  - `INSERT`
  - `UPDATE`
  - `DROP`
  - `CREATE`
  - backup
  - transaction
  - 本番データ投入

## TSV 読み込み

Program2 は `validate-tsv` と同じ厳密検証を再実装しない。

ただし最低限、以下8列がヘッダに存在することは確認する。列順は問わず、`03-1-import-metrics-sinta.php` と同様にヘッダ名ベースで読む。

```text
metric_source
metric_country
sealib_name
sealib_o_name
sealib_id
grade
url
note
```

方針:

- UTF-8 TSV として読む。
- 先頭ヘッダの UTF-8 BOM は除去する。
- 空行はスキップする。
- 列数不足はヘッダ数まで空文字でパディングする。
- 必須8列が存在しない場合はファイル全体をエラー終了する。
- 行単位の厳密検証は `validate-tsv` の責務であり、Phase 5B では重複実装しない。

## metric_source ホワイトリスト

Program2 側で `metric_source` の許可値を確認する。

初期候補:

```text
SINTA
THAI_TIER
SEALIB
MOCK
```

実装時には、最終的な許可値を `docs/program2-dry-run-design.md` / `../../sealib/docs/journal-metrics-semi-auto-design.md` の方針に合わせる。ホワイトリスト外は `invalid` とし、header 解決を行わない。

## header 解決ルール

名前優先・ID補助方式を実装する。

### 1. 行の事前判定

以下の場合は `invalid` とする。

- `metric_source` がホワイトリスト外
- `sealib_name` / `sealib_o_name` / `sealib_id` が全て空

`validate-tsv` 通過済みを前提にするため、Phase 5B では `metric_country` / `grade` / `note` 書式の厳密再検証はしない。

### 2. 名前候補取得

`sealib_name` と `sealib_o_name` の非空値を使い、`header.name` / `header.o_name` を完全一致で検索する。

取得列:

```sql
SELECT id, name, o_name
FROM header
WHERE name = :value OR o_name = :value
```

複数の検索値を使う場合は `id` で重複除去する。

### 3. 候補1件

- `sealib_id` が空、または候補 `id` と一致
  - `ready_to_insert`
- `sealib_id` が非空、かつ候補 `id` と不一致
  - `warning`
  - 候補を採用し、`id mismatch` を message に残す。

### 4. 候補複数

- `sealib_id` が非空、かつ候補集合内の `id` と一致
  - `ready_to_insert`
  - `resolution_method=disambiguated_by_sealib_id` 相当の message を残す。
- `sealib_id` が空、または候補集合内に一致しない
  - `ambiguous`
  - INSERT 予定行は生成しない。

### 5. 候補0件

- `sealib_id` が非空の場合、`header.id = :sealib_id` で fallback 検索する。
  - 見つかる場合:
    - `warning`
    - fallback 候補を採用し、`name mismatch` を message に残す。
  - 見つからない場合:
    - `unmatched`
- `sealib_id` が空の場合:
  - `unmatched`

## 分類

| category | 意味 | INSERT予定行 |
| --- | --- | --- |
| `ready_to_insert` | header を一意に解決でき、懸念なし | 生成する |
| `warning` | 採用可能だが id/name 不一致などの注意あり | 生成する |
| `ambiguous` | 複数候補を一意化できない | 生成しない |
| `unmatched` | header を解決できない | 生成しない |
| `invalid` | TSV行として Program2 側の最低条件を満たさない | 生成しない |

## INSERT 予定行

`ready_to_insert` / `warning` のみ、以下の予定行をメモリ上で生成する。

```text
ref_id
ref_name
metric_source
metric_country
grade
url
note
imported_at
```

値:

- `ref_id`: 解決後 `header.id`
- `ref_name`: 解決後 `header.name`
- `metric_source`: TSV `metric_source`
- `metric_country`: TSV `metric_country`
- `grade`: TSV `grade`
- `url`: TSV `url`
- `note`: TSV `note`
- `imported_at`: `null`

`mid` は AUTOINCREMENT であり dry-run では生成しない。`imported_at` も本番投入時に付与するため、Phase 5B dry-run では現在時刻を入れない。

## 標準出力 summary

実行終了時に以下を標準出力する。

```text
[ext] /path/to/sqlite_library_seas_ext.db
rows = 10
ready_to_insert = 6
warnings = 1
ambiguous = 1
unmatched = 1
invalid = 1
planned_insert_rows = 7
```

`planned_insert_rows` は `ready_to_insert + warning` とする。

## TSV レポート

`--report` が指定された場合、行ごとの dry-run 結果を TSV で出力する。

列案:

```text
line_no
category
metric_source
sealib_name
sealib_o_name
sealib_id
resolved_ref_id
resolved_ref_name
metric_country
grade
url
note
message
```

方針:

- `ready_to_insert` / `warning` は `resolved_ref_id` / `resolved_ref_name` を埋める。
- `ambiguous` / `unmatched` / `invalid` は解決列を空にし、`message` に理由を入れる。
- report 出力はファイル書き込みだが、DB 書き込みではない。既存 report がある場合の上書き可否は実装時に明示する。

## exit code

- `ambiguous` / `unmatched` / `invalid` が1件以上ある場合:
  - exit code `1`
- `warning` のみ、または `ready_to_insert` のみの場合:
  - exit code `0`
- CLI 引数不備、input 不読、DB 不読、必須ヘッダ不足:
  - exit code `1`

## 検証計画

### 構文確認

```bash
php -l ../../sealib/seas-3.3.1/admin/import-data-ext/03-2-import-metrics.php
```

### 一時 SQLite DB 検証

本番 DB を使わず、一時 SQLite DB に最小の `header` テーブルを作って確認する。

検証ケース:

1. `ready_to_insert`
   - `sealib_name` が `header.name` に1件一致。
2. `warning`
   - 1件一致するが `sealib_id` が不一致。
   - または名前0件だが `sealib_id` fallback が成功。
3. `ambiguous`
   - `name` / `o_name` が複数 `header` に一致し、`sealib_id` で絞れない。
4. `unmatched`
   - 名前も `sealib_id` も一致しない。
5. `invalid`
   - `metric_source` がホワイトリスト外。
   - または `sealib_name` / `sealib_o_name` / `sealib_id` が全て空。

確認項目:

- `ready_to_insert` / `warning` で INSERT 予定行が生成される。
- `ambiguous` / `unmatched` / `invalid` で INSERT 予定行が生成されない。
- summary 件数が一致する。
- `--report` の TSV が期待列で出力される。
- `ambiguous` / `unmatched` / `invalid` がある場合 exit code 1。
- warning のみなら exit code 0。
- DB ファイルの更新時刻や `journal_metrics` 件数が変わらない。

### 実 SEALIB DB read-only 検証

実 DB パスが確認できる場合のみ、read-only で検証する。

対象候補:

```text
../../sealib/seas-3.3.1/admin/sqlite_library_seas_ext.db
../../sealib/seas-3.3.1/admin/sqlite_library_seas.db
```

方針:

- まず `ext` を優先する。
- 必要に応じて `core` でも同じ TSV を試す。
- 実 DB には絶対に書き込まない。
- 本番データ投入は行わない。

## 非対象

- DB 書き込み
- DELETE / INSERT
- backup
- transaction
- REST API / OAI-PMH 変更
- journal-metrics-tools 側の変更
- `validate-tsv` の変更
- Program2 本番投入モード
- 本番データ投入

## Phase 5C で実装すべき最小作業候補

Phase 5B の dry-run が検証できた後、Phase 5C では本番投入モードを別タスクとして設計・実装する。

候補:

1. `03-2-import-metrics.php` の非 dry-run モード設計。
2. backup 必須化。
3. DB 単位 transaction。
4. TSV 内に出現する `metric_source` 単位の `DELETE WHERE metric_source = :source`。
5. `ready_to_insert` / `warning` のみ INSERT。
6. `imported_at` 付与。
7. 投入後件数検証。
8. ログ出力。
9. 実 DB での dry-run → backup → 少数投入 → rollback/復旧手順の確認。
