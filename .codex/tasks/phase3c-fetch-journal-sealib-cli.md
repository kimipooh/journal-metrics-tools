# Phase 3C: fetch-journal --adapter sealib 接続設計タスク

## 目的

Phase 3B で実装した `adapters/sealib.py` を `journal_metrics.py` の `fetch-journal` パイプラインへ接続する前に、CLI 引数・処理分岐・検証方法を固定する。

この Phase 3C は **設計のみ** とし、`journal_metrics.py`、`adapters/sealib.py`、既存 Excel、SEALIB DB への変更は行わない。本番データ投入もまだ必須ではない。

## 必ず読むファイル

- `journal_metrics.py`
- `adapters/sealib.py`
- `adapters/mock.py`
- `journal_mapper.py`
- `docs/adapter-contract.md`
- `.codex/tasks/phase3a-sealib-adapter-design.md`

## 現状確認

現行 `journal_metrics.py` の `fetch-journal` は Phase 2D の mock 専用実装である。

- `from adapters.mock import fetch_journal as fetch_mock_journal` のみを import している。
- `fetch_journal_command()` 冒頭で `args.adapter != "mock"` をエラーにしている。
- `argparse` の `--adapter` は `choices=["mock"]`。
- 対象行は `main.status` が空または `pending` の行。
- query は `main.journal_name` 優先、空なら `main.name`。
- `main_row_id` は Excel 行番号。
- adapter envelope は `journal_mapper.map_envelope_to_journal_rows()` に渡す。
- `append_journal_rows()` で `journal` シートへ追記する。
- `MAIN_STATUS_BY_ENVELOPE_STATUS` で `main.status` を `fetched` / `multiple_candidates` / `not_found` / `adapter_error` に更新する。
- workbook は `--input` へ保存する。

Phase 3C 実装では、上記の mock 既存挙動を壊さず、adapter 呼び出し部分だけを `mock` / `sealib` で分岐する。

## 設計する CLI

SEALIB adapter 接続:

```bash
.venv/bin/python journal_metrics.py fetch-journal \
  --input journal_metrics.xlsx \
  --adapter sealib \
  --db-path /path/to/sealib.sqlite
```

国/地域絞り込みあり:

```bash
.venv/bin/python journal_metrics.py fetch-journal \
  --input journal_metrics.xlsx \
  --adapter sealib \
  --db-path /path/to/sealib.sqlite \
  --country Indonesia
```

mock adapter は既存どおり:

```bash
.venv/bin/python journal_metrics.py fetch-journal \
  --input journal_metrics.xlsx \
  --adapter mock
```

## CLI 引数仕様

### `--adapter`

- `choices=["mock", "sealib"]` に拡張する。
- `mock` は既存挙動を維持する。
- `sealib` の場合のみ `--db-path` を必須扱いにする。

### `--db-path`

- `fetch-journal` サブコマンドに任意引数として追加する。
- `argparse` 上は `required=False` とし、`--adapter sealib` のときだけ実行時に必須チェックする。
- `--adapter sealib` かつ未指定の場合は、workbook を開く前に分かりやすいエラーで停止する。
- エラーメッセージ案:

```text
--db-path is required when --adapter sealib
```

理由:

- `--adapter mock` では DB が不要であり、`--db-path` を要求しない。
- adapter contract 上、`adapters.sealib.fetch_journal()` 自体は `db_path` 未指定を `adapter_error` envelope として返せるが、CLI では利用者の指定漏れを早期に明示するほうが分かりやすい。

### `--country`

- `fetch-journal` サブコマンドに任意引数として追加する。
- `--adapter sealib` の場合のみ `adapters.sealib.fetch_journal(..., country=args.country)` に渡す。
- `--adapter mock` では無視するか、後続の共通引数として存在していても使わない。
- 値はそのまま SEALIB adapter に渡し、adapter 側で `UPPER(country) = UPPER(?)` の絞り込みに使う。

## 実装方針

### import

候補:

```python
from adapters.mock import fetch_journal as fetch_mock_journal
from adapters.sealib import fetch_journal as fetch_sealib_journal
```

### adapter 呼び出し分岐

既存処理のうち、query 決定後の adapter 呼び出しだけを分岐する。

候補:

```python
if args.adapter == "mock":
    envelope = fetch_mock_journal(query)
elif args.adapter == "sealib":
    envelope = fetch_sealib_journal(
        query,
        db_path=args.db_path,
        country=args.country,
    )
else:
    raise ValueError(f"Unsupported adapter: {args.adapter}")
```

または小さな helper を追加する。

```python
def fetch_adapter_envelope(args: argparse.Namespace, query: str) -> dict:
    ...
```

最小実装では、不要な抽象化を避けるため `fetch_journal_command()` 内の局所分岐でよい。今後 SINTA / Thai Tier が増える段階で helper 化を検討する。

### `--db-path` 必須チェック

`fetch_journal_command()` の先頭付近で、既存の `args.adapter != "mock"` エラーを置き換える。

候補:

```python
if args.adapter == "sealib" and not args.db_path:
    raise ValueError("--db-path is required when --adapter sealib")
```

このチェックは workbook 読み込み前に実行する。指定漏れ時に Excel を開かず、既存ファイルへ副作用を出さないため。

## 共有する既存処理

`--adapter sealib` でも、adapter 呼び出し以降は mock と同じ処理を使う。

- `map_envelope_to_journal_rows(envelope, main_row_id=excel_row_number)`
- `append_journal_rows(journal_ws, journal_rows, JOURNAL_HEADERS)`
- `MAIN_STATUS_BY_ENVELOPE_STATUS[envelope["status"]]` による `main.status` 更新
- workbook 保存
- `Processed main rows`
- `Appended journal rows`
- `Adapter: sealib`

`main_row_id` は引き続き Excel 行番号を使う。

## status と journal 行の期待

`adapters.sealib.fetch_journal()` の envelope status は `journal_mapper.py` と既存 `MAIN_STATUS_BY_ENVELOPE_STATUS` にそのまま対応する。

| SEALIB envelope status | `journal.fetch_status` | `main.status` |
| --- | --- | --- |
| `fetched` | `ok` | `fetched` |
| `multiple_candidates` | `multiple` | `multiple_candidates` |
| `not_found` | `none` | `not_found` |
| `adapter_error` | `error` | `adapter_error` |

`not_found` / `adapter_error` でも `journal_mapper.py` は envelope 由来の 1 行を `journal` シートへ出す。Phase 3C 実装でもこの既存挙動を維持する。

## 本番データ投入の扱い

- 本番データ投入はまだ必須ではない。
- 実 SEALIB DB が見つからない場合は、一時 SQLite DB で検証してよい。
- 実 SEALIB DB パスが分かる段階で、read-only 接続による追加検証を行う。
- Phase 3C 実装は SEALIB DB への書き込み、`journal_metrics` テーブル参照、convert/import を行わない。

## 非対象

- SINTA / Thai Tier 接続
- grade 正規化
- `journal_metrics` テーブル参照
- DB 書き込み
- `convert`
- `enrich-db`
- `candidate_rank`
- `metrics_excel.py` の変更
- `README.md` の変更
- 本番データ投入

## 検証計画

### 1. py_compile

```bash
.venv/bin/python -m py_compile \
  journal_metrics.py \
  journal_mapper.py \
  adapters/mock.py \
  adapters/sealib.py
```

### 2. mock adapter の既存検証

既存 Phase 2D と同じ流れで、mock の 4 パターンが壊れていないことを確認する。

```bash
.venv/bin/python journal_metrics.py template --output /tmp/journal-metrics-mock.xlsx
```

検証用に `main` シートへ次の `journal_name` を `pending` で入れる。

- `normal journal`
- `multiple journal`
- `notfound journal`
- `error journal`

実行:

```bash
.venv/bin/python journal_metrics.py fetch-journal \
  --input /tmp/journal-metrics-mock.xlsx \
  --adapter mock
```

期待:

- `Processed main rows: 4`
- `Appended journal rows: 5`
- `Adapter: mock`
- `main.status` が `fetched` / `multiple_candidates` / `not_found` / `adapter_error`
- 2回目実行で `Processed main rows: 0` / `Appended journal rows: 0`

### 3. sealib adapter の db-path 未指定

```bash
.venv/bin/python journal_metrics.py fetch-journal \
  --input /tmp/journal-metrics-sealib.xlsx \
  --adapter sealib
```

期待:

- `--db-path is required when --adapter sealib` 相当の分かりやすいエラーになる。
- workbook を更新しない。

### 4. 一時 SQLite DB による sealib adapter 検証

実 SEALIB DB がない場合は、一時 SQLite DB を作成し、最小 `header` テーブルを用意して検証する。

サンプル schema:

```sql
CREATE TABLE header (
  id TEXT,
  name TEXT,
  o_name TEXT,
  issn TEXT,
  country TEXT
);
```

サンプル行:

| id | name | o_name | issn | country |
| --- | --- | --- | --- | --- |
| 1 | Journal Alpha | Alpha Original | 1111-1111 | Indonesia |
| 2 | Journal Beta | Beta Original | 2222-2222 | Indonesia |
| 3 | Journal Beta Studies |  | 3333-3333 | Thailand |

`main` シートに次を `pending` で入れる。

- `Alpha` → `fetched`
- `Beta` → `multiple_candidates`
- `Missing` → `not_found`

実行:

```bash
.venv/bin/python journal_metrics.py fetch-journal \
  --input /tmp/journal-metrics-sealib.xlsx \
  --adapter sealib \
  --db-path /tmp/sealib-phase3c.sqlite
```

期待:

- `Processed main rows: 3`
- `Appended journal rows: 4`
  - `Alpha`: 1 行
  - `Beta`: 2 行
  - `Missing`: `not_found` envelope 由来 1 行
- `main.status` が `fetched` / `multiple_candidates` / `not_found`
- `journal.journal_type` は `SEALIB`
- `journal.external_journal_id` は `header.id`
- `journal.journal_name` は `header.name`
- `journal.raw_json` に `issn` / `country` / `note` が保持される。
- 2回目実行で `Processed main rows: 0` / `Appended journal rows: 0`

### 5. `--country` 検証

同じ一時 SQLite DB で `--country Indonesia` を指定する。

```bash
.venv/bin/python journal_metrics.py fetch-journal \
  --input /tmp/journal-metrics-sealib-country.xlsx \
  --adapter sealib \
  --db-path /tmp/sealib-phase3c.sqlite \
  --country Indonesia
```

期待:

- `Beta` は Indonesia の 1 件だけに絞られ、`fetched` になる。
- country 比較は adapter 側の `UPPER(country) = UPPER(?)` に従う。

### 6. 実 SEALIB DB 検証

実 SEALIB DB パスがある場合のみ実施する。

- 実 DB は read-only 接続で参照する。
- 存在しそうな誌名 query で `fetched` / `multiple_candidates` / `not_found` のいずれかが返ることを確認する。
- `candidate` が contract のフィールドを持つことを確認する。
- DB 書き込みや本番データ投入は行わない。

### 7. 変更なし確認

```bash
git diff -- metrics_excel.py README.md
git diff --check
git status --short --untracked-files=all
```

期待:

- `metrics_excel.py` / `README.md` に変更がない。
- Phase 3C 実装時の差分は `journal_metrics.py` に限定される想定。
- Phase 3C 設計タスク作成時点では既存ファイルを変更しない。

## Phase 3C 実装で行う最小作業

1. `journal_metrics.py` に `from adapters.sealib import fetch_journal as fetch_sealib_journal` を追加する。
2. `fetch-journal --adapter` の choices を `["mock", "sealib"]` にする。
3. `fetch-journal` に `--db-path` を追加する。
4. `fetch-journal` に `--country` を追加する。
5. `--adapter sealib` かつ `--db-path` 未指定なら workbook 読み込み前にエラーにする。
6. query 決定後、`args.adapter` に応じて `fetch_mock_journal()` または `fetch_sealib_journal(query, db_path=args.db_path, country=args.country)` を呼ぶ。
7. mapper、journal 追記、main.status 更新、保存、標準出力は既存処理を共有する。
8. mock 既存検証と一時 SQLite DB 検証を行う。

## 完了条件

- `.codex/tasks/phase3c-fetch-journal-sealib-cli.md` が存在する。
- `--adapter sealib` の CLI 仕様が明記されている。
- `--db-path` と `--country` の扱いが明記されている。
- mock 既存挙動を維持する方針が明記されている。
- 実 DB がない場合の一時 SQLite DB 検証方針が明記されている。
- Phase 3C 実装の最小作業が定義されている。
- Phase 3C 設計時点では既存コード、`metrics_excel.py`、`README.md` を変更しない。

## Suggested Commit Message

```text
docs: define Phase 3C SEALIB fetch-journal CLI task
```
