# Phase 3A: SEALIB adapter 実装前の調査・設計タスク

## 目的

mock adapter で動いた `fetch-journal` パイプラインに、次の実ソースとして SEALIB adapter を接続する前に、SEALIB 側の入力・取得元・返却形式・read-only 境界を整理する。

この Phase 3A は **調査・設計のみ** とし、`adapters/sealib.py`、`journal_metrics.py`、既存 DB、既存 Excel への変更は行わない。本番データ投入もまだ不要である。

## 必ず読むファイル

- `docs/adapter-contract.md`
- `docs/rebuild-plan.md`
- `journal_metrics.py`
- `journal_mapper.py`
- `adapters/mock.py`
- `README.md`
- 旧 `metrics_excel.py`

## 旧 `metrics_excel.py` から確認した SEALIB 関連処理

### read_sealib_rows

旧実装の `read_sealib_rows(db_path: Path, country: str)` は、SQLite DB を read-only URI で開き、SEALIB `header` テーブルから対象国の journal header 行を読み取る。

確認した要点:

- `db_path.resolve()` で実パス化する。
- `urllib.parse.quote()` で file URI 用にパスをエスケープする。
- SQLite URI は `file:<path>?mode=ro` を使い、`sqlite3.connect(uri, uri=True)` で接続する。
- `conn.row_factory = sqlite3.Row` を設定する。
- 実行する SQL は `SELECT id, name, o_name, issn FROM header WHERE UPPER(country) = UPPER(?) ORDER BY id`。
- `finally` で必ず `conn.close()` する。
- 書き込み SQL、DDL、UPDATE、INSERT、DELETE は行わない。

この方式は SEALIB adapter の read-only DB 接続方針として流用候補とする。ただし Phase 3A では DB へ接続しない。

### normalized_grade

旧実装の `normalized_grade(raw)` は SINTA 向けの export 時正規化であり、`S1` / `Sinta 1` / `S1 Accredited` などを `S1 Accredited` に寄せ、未知値は raw 値のまま warning を返す。

SEALIB adapter ではこの関数を直接使わない。`docs/adapter-contract.md` の方針どおり、adapter は `grade` をソース表記の raw 値で返し、grade 正規化は `fetch-journal` 側に残す。将来の正規化は `journal_type` 別に行う。

### SEALIB DB 参照

旧 `init` は SEALIB `header` から `id`, `name`, `o_name`, `issn` を取得し、旧対応表の `sealib_id`, `sealib_name`, `sealib_o_name`, `issn` に展開していた。

旧実装で確認できる SEALIB 側の主な参照項目:

- `header.id`
- `header.name`
- `header.o_name`
- `header.issn`
- `header.country`

旧 `README.md` と `docs/rebuild-plan.md` では、SEALIB DB 参照は `--db-path` 明示必須、read-only SELECT、DB への書込なしという運用方針が示されている。

### read-only 境界

SEALIB adapter の read-only 境界は次のとおり定義する。

- DB 接続は SQLite URI `mode=ro` を使う。
- adapter は SELECT のみを実行する。
- adapter は SEALIB DB へ INSERT / UPDATE / DELETE / DDL を実行しない。
- adapter は `journal_metrics` へ投入しない。
- adapter は Excel を開かない、保存しない、更新しない。
- adapter は検索結果を adapter contract の envelope と candidates として返すだけに留める。
- 本番データ投入は convert/import 側の後続 Phase で扱う。Phase 3A/3B の SEALIB adapter では不要。

### 既存 journal_metrics / header / metrics 関連の結合キー

旧 workflow では `header.id` を旧対応表の `sealib_id` として保持し、export TSV では `sealib_id` を出力していた。

`docs/rebuild-plan.md` §8 では、新 `convert` から SEALIB `journal_metrics` への既定マッピングとして次が示されている。

| 新 convert | SEALIB `journal_metrics` |
| --- | --- |
| `id` | `ref_id` |
| `journal_name` | `ref_name` |
| `journal_type` | `metric_source` |
| `grade` | `grade` |
| `profile_url` | `url` |
| `note` | `note` |

Phase 3A の SEALIB adapter は `header.id` を candidate の `external_journal_id` として返す案を基本とする。将来 `convert` / `enrich-db` / import で `header.id`、`main.id`、`journal_metrics.ref_id` の対応を扱うが、Phase 3A では DB 投入や結合更新は行わない。

## SEALIB adapter の責務

SEALIB adapter は、検索クエリを受け取り、SEALIB DB から read-only に候補を検索し、`docs/adapter-contract.md` の envelope + candidates 形式で返す。

責務:

- Excel I/O はしない。
- SEALIB DB は read-only で参照する。
- adapter contract の envelope を返す。
- 候補は adapter contract の candidate フィールドに揃える。
- `grade` は raw 値で返す。
- `grade` 正規化は `fetch-journal` 側に残す。
- `source` は既定で `SEALIB` とする。
- 0 件、1 件、複数件、adapter error を contract の status 語彙へ変換する。

非責務:

- `main` / `journal` / `convert` シートの読み書き。
- `main.status` や `journal.fetch_status` の更新。
- `raw_json` の生成や保存。
- `main_row_id` の付与。
- DB import 用 TSV/SQL の生成。
- SEALIB DB への書き込み。

## 候補実装場所

候補ファイル:

- `adapters/sealib.py`

候補関数:

```python
def fetch_journal(
    query: str,
    source: str = "SEALIB",
    db_path: str | None = None,
) -> dict:
    ...
```

検討事項:

- `db_path` は Phase 3B の最小実装では必須扱いにするか、環境変数等を許可するかを決める。
- `db_path is None` の場合は `adapter_error` envelope を返すか、呼び出し側で引数必須エラーにする。
- `source` は mock adapter と同じく引数で上書き可能にしつつ、既定値は `SEALIB` とする。
- DB 接続・SQL・行から candidate への変換は `adapters/sealib.py` 内に閉じる。

## SEALIB で検索に使うキー

Phase 3B の最小検索キー案:

1. `query` を `main.journal_name` として扱う。
2. `main.journal_name` が空の場合は、既存 `fetch-journal` と同様に呼び出し側が `main.name` を query として渡す。
3. SEALIB adapter 内では `header.name` と `header.o_name` の検索を優先候補にする。
4. ISSN が main にある場合の扱いは後続検討とし、Phase 3B 最小実装では関数シグネチャが `query: str` のため ISSN を直接受け取らない。

ISSN の扱い:

- 現行 `fetch-journal` は `query` 文字列だけを adapter に渡すため、`main.issn` を adapter に直接渡せない。
- Phase 3B では title/name 検索を最小実装にする。
- ISSN 検索を使う場合は、後続で adapter 入力を `query` 以外の構造化引数へ拡張するか、`fetch-journal` 側で ISSN を優先 query として渡す設計変更が必要になる。
- SEALIB `header.issn` は candidate の `issn` へ返す。
- SEALIB `header` に `eissn` は無い前提なので、candidate の `eissn` は `null` とする。

将来的な ID の扱い:

- `header.id` は SEALIB 側の stable ID とみなし、candidate の `external_journal_id` に入れる。
- `main.id` は将来 `header.id` / `journal_metrics.ref_id` と対応しうるが、Phase 3A/3B では更新しない。
- `journal_metrics.ref_id` への投入・照合は `convert` または import 側の後続タスクで扱う。

## adapter contract candidate フィールドへのマッピング案

| candidate フィールド | SEALIB 由来 | 方針 |
| --- | --- | --- |
| `source` | 固定値 | `"SEALIB"` |
| `external_journal_id` | `header.id` | 文字列化して返す |
| `title` | `header.name` 優先、必要なら `header.o_name` | 候補名。空の場合は候補として扱わない方針を検討 |
| `issn` | `header.issn` | 空なら `null` |
| `eissn` | 対応列なし | `null` |
| `publisher` | 対応列なし | `null` |
| `country` | `header.country` | 検索 SQL で取得する場合は raw 値を返す。Phase 3B で列取得に含めるか検討 |
| `grade` | SEALIB 既存 metrics 由来、または対応なし | Phase 3B で `journal_metrics` も参照するなら raw 値を返す。`header` のみなら `null` |
| `url` | 対応列なし | `null` |
| `note` | 補足 | `header.o_name` や match reason を入れるか検討。直接列にない情報は `raw_json` で保持される |

Phase 3B の最小実装では、まず `header` ベースの候補検索に絞り、`grade` は `null` とする案が安全である。SEALIB 既存 `journal_metrics` から最新 grade を引く必要がある場合は、結合条件と重複時の優先順位を別途定義する。

## envelope status 方針

| 検索結果 | `envelope.status` | `candidates` | `error` |
| --- | --- | --- | --- |
| 1 件 | `fetched` | 1 件 | `null` |
| 0 件 | `not_found` | 空配列 | `null` |
| 2 件以上 | `multiple_candidates` | 複数件 | `null` |
| DB パス未指定、DB 接続失敗、SQL 失敗 | `adapter_error` | 空配列 | エラーメッセージ |

## 非対象

- 今回は `adapters/sealib.py` を実装しない。
- 今回は `journal_metrics.py` を変更しない。
- 今回は `journal_mapper.py` を変更しない。
- 今回は `adapters/mock.py` を変更しない。
- 今回は DB に接続しない。
- 今回は SINTA / Thai Tier に接続しない。
- 今回は `convert` / `enrich-db` を実装しない。
- 今回は SEALIB `journal_metrics` へ投入しない。
- 今回は TSV / SQL export を実装しない。
- 本番データ投入はまだ行わない。

## Phase 3B の次タスク

Phase 3B では、SEALIB adapter の最小実装を行う。

最小作業:

1. `adapters/sealib.py` を新規作成する。
2. `fetch_journal(query: str, source: str = "SEALIB", db_path: str | None = None) -> dict` を実装する。
3. SQLite DB を `mode=ro` で read-only 接続する。
4. `header.name` / `header.o_name` を対象に query 検索する。
5. 結果 1 件を `fetched`、0 件を `not_found`、複数件を `multiple_candidates` として返す。
6. DB パス未指定、接続失敗、SQL 失敗は `adapter_error` として返す。
7. candidate フィールドを adapter contract に合わせる。
8. DB への書き込みが発生しないことを確認する。

`fetch-journal --adapter sealib` への接続は Phase 3B に含めてもよいが、さらに後続タスクに分けてもよい。最小実装では adapter 単体テストを優先し、既存 `journal_metrics.py` の mock-only 動作を壊さない。

## 検証手順

Phase 3A の検証:

```bash
test -f .codex/tasks/phase3a-sealib-adapter-design.md
git diff --name-only
git diff --check
git status --short
```

期待:

- `.codex/tasks/phase3a-sealib-adapter-design.md` が作成されている。
- 既存コードファイルに変更がない。
- SEALIB adapter の read-only 境界が明記されている。
- adapter contract へのマッピング方針が明記されている。
- 本番データ投入がまだ不要であることが明記されている。

## 完了条件

- Phase 3A の調査・設計タスクが `.codex/tasks/phase3a-sealib-adapter-design.md` として存在する。
- 旧 `metrics_excel.py` の `read_sealib_rows`、`normalized_grade`、SEALIB DB 参照、read-only 境界、既存結合キーが整理されている。
- SEALIB adapter の責務と非責務が明記されている。
- `adapters/sealib.py` と `fetch_journal(...)` の候補実装場所・候補関数が明記されている。
- 検索キー、ISSN、将来の `ref_id` / `header.id` / `journal_metrics.ref_id` の扱いが整理されている。
- candidate フィールドへのマッピング案がある。
- Phase 3B の最小実装タスクが定義されている。
- `adapters/sealib.py`、`journal_metrics.py`、DB 接続、本番データ投入は行っていない。

## Suggested Commit Message

```text
docs: define Phase 3A SEALIB adapter design task
```
