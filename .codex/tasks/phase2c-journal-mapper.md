# Phase 2C: Journal Mapper 実装タスク

## 目的

`fetch-journal` の Excel 書き込みを実装する前に、adapter contract の envelope を `journal` シート 1 行相当の dict 配列へ変換する責務を切り出す。

Phase 2C では、adapter から返る `envelope` と `main_row_id` を受け取り、`journal` シートのヘッダに対応する行 dict を返す pure Python の mapper を実装する。Excel I/O、`openpyxl` 操作、CLI 追加は行わない。

## 実装対象

- `journal_mapper.py`（新規作成）

既存ファイルは原則変更しない。特に `journal_metrics.py` / `metrics_excel.py` / `README.md` は変更しない。

## 関数仕様

```python
def map_envelope_to_journal_rows(envelope: dict, main_row_id: int) -> list[dict]:
    ...
```

入力:

- `envelope`: `docs/adapter-contract.md` に準拠した adapter envelope。
- `main_row_id`: `main` シート行への参照。adapter は扱わず、mapper 呼び出し側が渡す。

出力:

- `journal` シート 1 行に対応する dict の配列。
- dict の key は Phase 1 の `journal` ヘッダに対応させる。

## 出力 dict の列

各 row dict は次の key を持つ。

- `main_row_id`
- `journal_type`
- `external_journal_id`
- `journal_name`
- `affiliation`
- `grade`
- `profile_url`
- `fetch_status`
- `fetched_at`
- `raw_json`

Phase 1 の `journal` シートヘッダ順は `journal_metrics.py` の `JOURNAL_HEADERS` に従う。mapper は dict を返すだけで、列順制御や Excel 書き込みは行わない。

## 変換ルール

### status mapping

`envelope.status` から `fetch_status` を決定する。

| `envelope.status` | `fetch_status` |
| --- | --- |
| `fetched` | `ok` |
| `multiple_candidates` | `multiple` |
| `not_found` | `none` |
| `adapter_error` | `error` |

未知の `envelope.status` の扱いは実装時に明示する。最小実装では `ValueError` で失敗させる。

### candidate あり

- `fetched` は 1 candidate から 1 row を返す。
- `multiple_candidates` は candidate 数分の row を返す。
- 1 candidate = 1 journal row とする。
- `candidate_rank` は扱わない。
- candidate 配列順を保持して row 配列へ変換する。

candidate から row への対応:

| candidate | journal row |
| --- | --- |
| `source` | `journal_type` |
| `external_journal_id` | `external_journal_id` |
| `title` | `journal_name` |
| `publisher` | `affiliation` |
| `grade` | `grade` |
| `url` | `profile_url` |
| candidate 全体 | `raw_json` |

`issn` / `eissn` / `country` / `note` は直接対応列を持たないため、`raw_json` に candidate 全体を JSON 文字列として保存する。

### candidate なし

`not_found` / `adapter_error` の場合も、監査ログとして 1 row を返す。

理由:

- `main_row_id` 単位で fetch が実行された事実を `journal` シートに残せる。
- 0 件とエラーを `fetch_status` で追跡できる。
- 後続の `fetch-journal` 実装で、Excel 書き込み層が「0 rows の場合だけ別処理」を持たずに済む。

row 内容:

- `main_row_id`: 引数の値
- `journal_type`: `envelope.source`
- `external_journal_id`: `None`
- `journal_name`: `envelope.query`
- `affiliation`: `None`
- `grade`: `None`
- `profile_url`: `None`
- `fetch_status`: `none` または `error`
- `fetched_at`: ISO 8601 文字列
- `raw_json`: envelope 全体を JSON 文字列化したもの

## raw_json

- candidate がある場合は、candidate オブジェクト全体を JSON 文字列として `raw_json` に保存する。
- `not_found` / `adapter_error` のように candidate がない場合は、envelope 全体を JSON 文字列として `raw_json` に保存する。
- `json.dumps(..., ensure_ascii=False)` を使い、日本語などの非 ASCII 文字を保持できるようにする。
- JSON として parse 可能な文字列であることを検証する。

## fetched_at

- mapper が row 生成時刻を ISO 8601 文字列として設定する。
- 最小実装では timezone-aware UTC を推奨する。
- 例: `datetime.now(timezone.utc).isoformat()`
- 同一 envelope から複数 row を生成する場合、同一呼び出し内では同じ `fetched_at` を使う。

## 非対象

- Excel 書き込み
- `openpyxl` 操作
- `journal_metrics.py` への `fetch-journal` コマンド追加
- `main` シート読み取り
- `journal` シートへの追記
- `main.status` 更新
- SEALIB / SINTA / Thai Tier 接続
- adapter 呼び出し
- grade 正規化
- `candidate_rank` の追加
- スコアリングや候補順位管理
- adapter の抽象基底クラス作成
- dataclass 化
- `metrics_excel.py` の変更
- `README.md` の変更

## YAGNI

- `candidate_rank` は追加しない。
- スコアリングや候補順位管理はしない。
- adapter の抽象基底クラスは作らない。
- dataclass 化は必要になってから検討する。
- 先に Excel I/O を作り込まない。

## 検証項目

実装後は次を確認する。

- mock adapter の 4 パターンを mapper に渡せること。
- `fetched` は 1 行返ること。
- `multiple_candidates` は候補数分の行が返ること。
- `not_found` は `fetch_status == "none"` の 1 行を返すこと。
- `adapter_error` は `fetch_status == "error"` の 1 行を返すこと。
- 各 row が `journal` ヘッダに対応する key を持つこと。
- `raw_json` が JSON 文字列として `json.loads()` できること。
- candidate ありの `raw_json` には candidate 全体が保存されること。
- candidate なしの `raw_json` には envelope 全体が保存されること。
- `fetched_at` が ISO 8601 文字列であること。
- `candidate_rank` が row に含まれないこと。
- grade 正規化が行われず、candidate の raw `grade` がそのまま入ること。
- `journal_metrics.py` / `metrics_excel.py` / `README.md` に変更がないこと。

## 検証コマンド例

```bash
.venv/bin/python -m py_compile journal_mapper.py

.venv/bin/python - <<'PY'
import json
from adapters.mock import fetch_journal
from journal_mapper import map_envelope_to_journal_rows

required = {
    "main_row_id",
    "journal_type",
    "external_journal_id",
    "journal_name",
    "affiliation",
    "grade",
    "profile_url",
    "fetch_status",
    "fetched_at",
    "raw_json",
}

cases = {
    "normal journal": ("ok", 1),
    "multiple journal": ("multiple", 2),
    "notfound journal": ("none", 1),
    "error journal": ("error", 1),
}

for query, (expected_fetch_status, expected_count) in cases.items():
    rows = map_envelope_to_journal_rows(fetch_journal(query), main_row_id=10)
    assert len(rows) == expected_count, (query, rows)
    for row in rows:
        assert required <= set(row), row
        assert "candidate_rank" not in row, row
        assert row["main_row_id"] == 10, row
        assert row["fetch_status"] == expected_fetch_status, row
        json.loads(row["raw_json"])

print("ok")
PY
```

## 完了条件

- `journal_mapper.py` が新規作成されている。
- `map_envelope_to_journal_rows(envelope: dict, main_row_id: int) -> list[dict]` が実装されている。
- mock adapter の 4 パターンを row dict 配列へ変換できる。
- `not_found` / `adapter_error` も監査ログとして 1 row を返す。
- Excel 書き込みや CLI 追加は行われていない。
- `journal_metrics.py` / `metrics_excel.py` / `README.md` は変更されていない。

## Suggested Commit Message

```text
docs: define Phase 2C journal mapper implementation task
```
