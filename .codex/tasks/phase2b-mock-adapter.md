# Phase 2B: Mock Adapter 実装タスク

## 目的

`docs/adapter-contract.md` に準拠する mock adapter を実装する。外部 CLI・DB・ネットワークには接続せず、固定レスポンスで adapter contract の envelope と candidate 形式を Python コード上で検証できる状態にする。

この Phase 2B は、`fetch-journal` 本体の Excel 書き込みへ入る前の足場である。`journal_metrics.py` 側の Excel 書き込み、`fetch_status` 決定、`main_row_id` 付与、grade 正規化は後続 Phase で扱う。

## 対象ファイル候補

実装時の推奨追加ファイル:

- `adapters/`（新規ディレクトリ）
- `adapters/__init__.py`
- `adapters/mock.py`

既存ファイルは原則変更しない。特に `journal_metrics.py` / `metrics_excel.py` / `README.md` は Phase 2B では変更しない。

## 実装範囲

- `adapters.mock.fetch_journal()` を実装する。
- `docs/adapter-contract.md` §4 の envelope 形式を返す。
- 返却する candidate は contract の最小フィールドをすべて含める。
- query の内容により、4 種類の `envelope.status` を切り替える。
- 外部 CLI・DB・ネットワークを一切呼ばない。

## 関数仕様

```python
def fetch_journal(query: str, source: str = "MOCK") -> dict:
    ...
```

引数:

- `query`: 検索クエリ。`envelope.query` にそのまま入れる。
- `source`: 取得元識別子。既定は `"MOCK"`。`envelope.source` と各 candidate の `source` に入れる。

戻り値:

- `dict`
- 形式は `docs/adapter-contract.md` §4.3 の envelope に準拠する。

```python
{
    "status": "<fetched|multiple_candidates|not_found|adapter_error>",
    "source": source,
    "query": query,
    "candidates": [candidate, ...],
    "error": None or "<error message>",
}
```

## candidate フィールド

返却される candidate は、`docs/adapter-contract.md` §4.1 の最小フィールドをすべて含める。

- `source`
- `external_journal_id`
- `title`
- `issn`
- `eissn`
- `publisher`
- `country`
- `grade`
- `url`
- `note`

候補が存在する場合、`source` と `title` は空値不可とする。任意フィールドが不明な場合は空文字ではなく `None` を使う。

## envelope 4 パターン

### `fetched`

- 条件: query が `multiple` / `notfound` / `error` のいずれも含まない。
- `status`: `fetched`
- `candidates`: 1 件
- `error`: `None`

### `multiple_candidates`

- 条件: query に `multiple` を含む。
- `status`: `multiple_candidates`
- `candidates`: 2 件以上
- `error`: `None`
- 配列順が候補順を表す。`candidate_rank` は返さない。

### `not_found`

- 条件: query に `notfound` を含む。
- `status`: `not_found`
- `candidates`: `[]`
- `error`: `None`

### `adapter_error`

- 条件: query に `error` を含む。
- `status`: `adapter_error`
- `candidates`: `[]`
- `error`: 非 `None` のエラーメッセージ

## query による切り替え仕様

query の判定は小文字化して行う。

- `"multiple"` を含む → `multiple_candidates`
- `"notfound"` を含む → `not_found`
- `"error"` を含む → `adapter_error`
- それ以外 → `fetched`

優先順位は上から順にする。例えば `multiple error` は `multiple_candidates` として扱う。空文字や空白のみの query の扱いは実装時に明示する。最小実装では `fetched` として扱ってよいが、候補の `title` が空にならないように `"Mock Journal"` などの fallback を使う。

## main_row_id と candidate_rank の扱い

- mock adapter は `main_row_id` を扱わない。
- candidate オブジェクトにも envelope にも `main_row_id` は含めない。
- `main_row_id` は fetch-journal 側が `journal` シートへ書き込むときに付与する。
- `candidate_rank` は現時点では採用しない。
- 複数候補の順序は `envelope.candidates` 配列順で保持し、将来 fetch-journal が `journal` シート上の行順として反映する。

## 非対象

- `journal_metrics.py` への `fetch-journal` コマンド追加はしない。
- Excel への書き込みはしない。
- `main.status` / `journal.fetch_status` の更新はしない。
- `main_row_id` の付与はしない。
- `candidate_rank` 列の追加はしない。
- grade 正規化はしない。`grade` は mock の raw 値をそのまま返す。
- SEALIB / SINTA / Thai Tier には接続しない。
- 外部 CLI、DB、ネットワークには接続しない。
- `metrics_excel.py` は変更しない。
- `README.md` は変更しない。

## 検証項目

実装後は次を確認する。

- Python から `adapters.mock.fetch_journal()` を import して呼び出せること。
- 4 パターンの `envelope.status` が返ること。
  - 通常 query → `fetched`
  - `multiple` を含む query → `multiple_candidates`
  - `notfound` を含む query → `not_found`
  - `error` を含む query → `adapter_error`
- `fetched` と `multiple_candidates` の `candidates` が contract の candidate フィールドをすべて含むこと。
- `adapter_error` 時は `candidates == []` かつ `error is not None` であること。
- `not_found` 時は `candidates == []` かつ `error is None` であること。
- 候補内に `main_row_id` と `candidate_rank` が含まれないこと。
- `grade` が正規化されず raw 値として返ること。
- 外部 CLI、DB、ネットワーク接続が発生しないこと。
- `journal_metrics.py` / `metrics_excel.py` / `README.md` に変更がないこと。

## 検証コマンド例

```bash
.venv/bin/python - <<'PY'
from adapters.mock import fetch_journal

required = {
    "source",
    "external_journal_id",
    "title",
    "issn",
    "eissn",
    "publisher",
    "country",
    "grade",
    "url",
    "note",
}

cases = {
    "sample journal": "fetched",
    "multiple sample journal": "multiple_candidates",
    "notfound sample journal": "not_found",
    "error sample journal": "adapter_error",
}

for query, expected_status in cases.items():
    envelope = fetch_journal(query)
    assert envelope["status"] == expected_status, envelope
    assert envelope["source"] == "MOCK", envelope
    assert envelope["query"] == query, envelope
    assert isinstance(envelope["candidates"], list), envelope

    for candidate in envelope["candidates"]:
        assert required <= set(candidate), candidate
        assert "main_row_id" not in candidate, candidate
        assert "candidate_rank" not in candidate, candidate

assert fetch_journal("notfound sample journal")["candidates"] == []
assert fetch_journal("notfound sample journal")["error"] is None
assert fetch_journal("error sample journal")["candidates"] == []
assert fetch_journal("error sample journal")["error"] is not None

print("ok")
PY
```

必要に応じて、実装後に `python -m py_compile adapters/mock.py` も実行する。

## 完了条件

- `adapters/mock.py` に `fetch_journal(query: str, source: str = "MOCK") -> dict` が実装されている。
- `adapters/__init__.py` が存在し、`adapters.mock` を import できる。
- 4 パターンの envelope が `docs/adapter-contract.md` に準拠して返る。
- candidate が contract の最小フィールドをすべて含む。
- `main_row_id` / `candidate_rank` は adapter の返却値に含まれない。
- `journal_metrics.py` / `metrics_excel.py` / `README.md` は変更されていない。

## Suggested Commit Message

```text
docs: define Phase 2B mock adapter implementation task
```
