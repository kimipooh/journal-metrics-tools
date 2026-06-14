# Phase 2D: fetch-journal mock CLI 実装タスク

## 目的

Phase 2B の mock adapter、Phase 2C の journal mapper、Phase 2C-2 の `append_journal_rows()` を接続し、mock adapter だけを使う最小 `fetch-journal` CLI を実装する。

この Phase 2D では、`main` シートから対象行を読み、`adapters.mock.fetch_journal()` の envelope を `journal_mapper.map_envelope_to_journal_rows()` で journal row dict へ変換し、`append_journal_rows()` で `journal` シートへ追記する。実ソース adapter、grade 正規化、DB 連携、本番データ投入は扱わない。

## 設計するコマンド

```bash
.venv/bin/python journal_metrics.py fetch-journal --input journal_metrics.xlsx --adapter mock
```

引数:

- `--input`: 読み書きする `.xlsx` ファイル。最小実装では同じファイルへ保存する。
- `--adapter`: Phase 2D では `mock` のみ許可する。`mock` 以外はエラーにする。

## 実装対象

- `journal_metrics.py`

既存 helper を利用する:

- `JOURNAL_HEADERS`
- `append_journal_rows(ws, rows, JOURNAL_HEADERS)`
- `journal_mapper.map_envelope_to_journal_rows(envelope, main_row_id)`
- `adapters.mock.fetch_journal(query)`

## 実装範囲

1. `argparse` に `fetch-journal` サブコマンドを追加する。
2. `openpyxl.load_workbook()` で `--input` の workbook を開く。
3. `main` シートと `journal` シートを取得する。
4. `main` シートのヘッダ行から列名 index を作る。
5. `main` シートのデータ行を読む。
6. `status` が `pending` または空の行だけ対象にする。
7. 検索クエリは `main.journal_name` があればそれを使い、なければ `main.name` を使う。
8. adapter は `mock` のみ対応し、`adapters.mock.fetch_journal(query)` を呼ぶ。
9. `journal_mapper.map_envelope_to_journal_rows(envelope, main_row_id)` を呼ぶ。
10. `append_journal_rows(journal_ws, rows, JOURNAL_HEADERS)` で `journal` シートへ追記する。
11. workbook を `--input` に保存する。
12. 処理件数と追記件数を標準出力する。

## main_row_id の扱い

Phase 1 template の `main` ヘッダには `main_row_id` 列が存在しない。Phase 2D では **Excel の行番号を `main_row_id` として使う**。

理由:

- 既存の Phase 1 template を変更せずに使える。
- `journal.main_row_id` から `main` シート上の元行へ直接戻れる。
- 追加列なしで最小実装できる。

将来、永続 ID が必要になった場合は `main` シートに専用 ID 列を追加する別タスクで検討する。

## 対象行の条件

- `status` が空または `pending` の行を対象とする。
- `status` の比較は前後空白を除去し、小文字化して行う。
- `status` 列が存在しない場合はエラーにする。
- `journal_name` と `name` の両方が空の行はスキップする。

Phase 2D では `main.status` の更新は行わない。再実行時の重複追記対策は後続タスクで扱う。

## sheet / header の扱い

- `main` シートが存在しない場合はエラーにする。
- `journal` シートが存在しない場合はエラーにする。
- `main` ヘッダ行は 1 行目とする。
- `journal` ヘッダは既存 `JOURNAL_HEADERS` を使う。
- Phase 2D では `journal` シート既存ヘッダの自動修復は行わない。必要なら後続タスクで検討する。

## 標準出力

最小実装では、次のような要約を出力する。

```text
Processed main rows: 4
Appended journal rows: 5
Adapter: mock
```

エラー詳細や行別ログは必要になってから追加する。

## 非対象

- SINTA adapter 実装
- SEALIB adapter 実装
- Thai Tier adapter 実装
- 外部 CLI 呼び出し
- DB 読み書き
- grade 正規化
- `convert` シート
- `enrich-db`
- 本番データ投入
- `candidate_rank`
- `main.status` 更新
- 重複追記の防止
- journal 既存ヘッダの自動修復
- `metrics_excel.py` の変更
- README.md の変更

## 検証手順

### 1. template workbook 作成

```bash
.venv/bin/python journal_metrics.py template --output journal_metrics.xlsx
```

期待:

- `README` / `main` / `journal` / `convert` シートが生成される。
- 既存 template コマンドの挙動が壊れていない。

### 2. main シートにダミー 4 行を追加

検証用スクリプト例:

```bash
.venv/bin/python - <<'PY'
from openpyxl import load_workbook

wb = load_workbook("journal_metrics.xlsx")
ws = wb["main"]
headers = [cell.value for cell in ws[1]]
idx = {name: headers.index(name) + 1 for name in headers}

for name in ["normal journal", "multiple journal", "notfound journal", "error journal"]:
    row = [None] * len(headers)
    row[idx["journal_name"] - 1] = name
    row[idx["status"] - 1] = "pending"
    ws.append(row)

wb.save("journal_metrics.xlsx")
PY
```

### 3. fetch-journal mock 実行

```bash
.venv/bin/python journal_metrics.py fetch-journal --input journal_metrics.xlsx --adapter mock
```

期待:

- `Processed main rows: 4` 相当が出力される。
- `Appended journal rows: 5` 相当が出力される。
- workbook が保存される。

### 4. journal シート検証

```bash
.venv/bin/python - <<'PY'
from openpyxl import load_workbook

wb = load_workbook("journal_metrics.xlsx", read_only=True)
ws = wb["journal"]
headers = [cell.value for cell in ws[1]]
idx = {name: headers.index(name) + 1 for name in headers}

rows = list(ws.iter_rows(min_row=2, values_only=True))
statuses = [row[idx["fetch_status"] - 1] for row in rows]
raw_values = [row[idx["raw_json"] - 1] for row in rows]

print(len(rows))
print(statuses)
print(all(raw_values))
PY
```

期待:

- 追記行数は合計 5 行。
- `normal journal` は 1 行 `ok`。
- `multiple journal` は 2 行 `multiple`。
- `notfound journal` は 1 行 `none`。
- `error journal` は 1 行 `error`。
- `raw_json` が保存されている。

### 5. py_compile

```bash
.venv/bin/python -m py_compile journal_metrics.py journal_mapper.py adapters/mock.py
```

## 完了条件

- `fetch-journal --adapter mock` が `main` シートの対象行を読み取れる。
- `mock` adapter の 4 パターンを `journal` シートへ追記できる。
- 4 件の main ダミー行から journal へ合計 5 行追記される。
- `raw_json` が保存される。
- workbook が保存される。
- template コマンドの既存挙動が維持される。
- SINTA / SEALIB / Thai Tier / DB / 本番データには接続しない。
- `metrics_excel.py` は変更しない。
- README.md は変更しない。

## Suggested Commit Message

```text
docs: define Phase 2D mock fetch-journal CLI task
```
