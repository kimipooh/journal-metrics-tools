# Adapter Contract（Journal Metrics 取得アダプタ共通仕様）

> 本書は **contract 定義のみ**。v1.0.0 時点の実装済み adapter は `mock` / `sealib` / `sinta` のみ。

## 1. 目的

`fetch-journal` は、外部ソース（SINTA / SEALIB / 将来のソース）から Journal Metrics 候補を取得し、`journal` シートへ書き込む。本書は、その「取得」を担う **adapter** が満たすべき共通 contract（入出力形式・フィールド定義・status 語彙）を定義する。

adapter contract を固定することで、ソースごとの差異を adapter 内部に閉じ込め、`journal_metrics.py` 側（Excel 書き込み層）はソースを問わず同じ形式を扱える。

## 2. レイヤー分離

| レイヤー | 責務 |
| --- | --- |
| **adapter（外部ソース取得層）** | 検索クエリを受け取り、本書 §4 の共通形式（envelope + candidates）で結果を返す。ソース固有のスクレイピング/API呼び出し/DB読み取りはここに閉じる。 |
| **fetch-journal（Excel 書き込み層）** | main の対象行ごとに adapter を呼び出し、envelope を `journal` シートへ書き込む。`fetch_status` 決定、`grade` のソース横断正規化、`raw_json` 保存、`fetched_at` 設定を行う。 |

adapter は **Excel I/O を行わない**。`journal_metrics.py` は **ソース固有ロジックを持たない**。

## 3. 対応ソースと実装方針

adapter contract は SEALIB / SINTA / 将来ソースのいずれであっても同一の共通形式（§4）で結果を返す。adapter は各ソース固有の取得結果を共通フィールドへマッピングする。`grade` はソース表記の raw 値のまま返し、adapter は正規化を行わない（grade のソース横断正規化は fetch-journal 側 §2 の責務）。対応するフィールドが無いソースについては、当該フィールドを `null` として返すことで差異を吸収する。

- **mock adapter**: 外部接続を行わず、本 contract に準拠した固定/サンプル候補を返す。fetch-journal の実装・テストに用いる。
- **実ソース adapter**: **SEALIB adapter**（SEALIB 側の既存メトリクスデータを Journal Metrics ソースの一つとして読み取る用途を想定）、SINTA 等の外部 CLI 経由 adapter を同方針で追加する。
- 実装方式（in-process 関数 / 外部 CLI subprocess 等）は adapter ごとに個別に確定する。本書は **入出力形式のみ** を固定する。

## 4. 共通返却形式

### 4.1 候補（candidate）フィールド

1 候補 = 1 journal シート行に対応する。

現行 `journal_metrics.py` の `JOURNAL_HEADERS` は次の順序とする。

```text
main_row_id
journal_type
external_journal_id
journal_name
affiliation
grade
profile_url
fetch_status
fetched_at
raw_json
```

| フィールド | 意味 | 必須/任意 | 空値の扱い | `journal` シート対応列 |
| --- | --- | --- | --- | --- |
| `source` | 取得元識別子（`SINTA` / `SEALIB` 等） | **必須** | 空値不可 | `journal_type` |
| `external_journal_id` | ソース側の journal ID | 任意 | 不明時は `null`（Excel では空セル） | `external_journal_id` |
| `title` | 候補の名称（ソース表記） | **必須**（候補が存在する限り必須） | 空値不可 | `journal_name` |
| `issn` | Print ISSN | 任意 | 不明時は `null` | 直接対応列なし → `raw_json` に保持 |
| `eissn` | Electronic ISSN | 任意 | 不明時は `null` | 直接対応列なし → `raw_json` に保持 |
| `publisher` | 発行者/所属機関 | 任意 | 不明時は `null` | `affiliation`（既存列を再利用。「発行者」と「所属機関」の意味差はあるが、現状最も近い既存列として割当。差異が問題化した場合は別タスクで再検討） |
| `country` | 国/地域コード | 任意 | 不明時は `null` | 直接対応列なし → `raw_json` に保持 |
| `grade` | ソース表記の評価・等級（**正規化前の raw 値**） | 任意 | 対象外/不明時は `null` | `grade`（fetch-journal 側で `journal_type` 別の正規化を適用してから書き込む。adapter は正規化しない） |
| `url` | プロフィール/詳細ページ URL | 任意 | 不明時は `null` | `profile_url` |
| `note` | adapter からの補足情報（自由記述） | 任意 | 不明時は `null` | 直接対応列なし → `raw_json` に保持（`journal.note` 列の追加は本書スコープ外の将来検討事項） |

> **注記（`external_journal_id` の意味差異）**: `external_journal_id` は本 contract 上「ソース側の journal ID」として定義されているが、SEALIB adapter は例外的に SEALIB `header.id`（SEALIB DB の内部レコードID）をこのフィールドに格納する。SINTA 等の外部 source では文字通り外部サービスの journal ID を示す。この差異は `journal_metrics.py` の `convert_sealib_id()`（`metric_source == "SEALIB"` 分岐、L312-320）で吸収しており、SEALIB 行の場合のみ `journal.external_journal_id` を `convert.sealib_id` に昇格させ、SINTA 等の外部 source では `main.id` を `sealib_id` として使う。本挙動は既存 workbook との後方互換維持のために現時点では変更しない。将来的に `source_record_id` 等への名称整理を検討する可能性はあるが、現時点では設計上の注記に留める。

- JSON 上の空値は **`null`** を用いる（`""` ではない）。
- `journal.raw_json` には **candidate オブジェクト全体**（上記フィールドすべて）を JSON 文字列として保存する。直接対応列がないフィールド（`issn`/`eissn`/`country`/`note`）はこの `raw_json` 経由でのみ保持される。fetch-journal はトレーサビリティのため、候補行の `raw_json` に実際に adapter へ渡した `query` も保存する。

### 4.2 候補と journal 行の対応関係（main_row_id）

- **1 candidate = 1 `journal` シート行**。1 件の `main` 行に対し、`fetch-journal` は 0 件以上の candidate を `journal` シートへ複数行として書き込む（1:N）。
- `journal.main_row_id` で `main` 行と紐づける。複数候補が存在する場合は、同一 `main_row_id` を持つ `journal` シート上の行順で `envelope.candidates` 配列内の順序を保持する。
- **adapter の candidate オブジェクト（§4.1）には `main_row_id` を含めない**。adapter は呼び出し元の `main` 行を意識しない。
- `main_row_id` は **fetch-journal（Excel 書き込み層）が付与する**。fetch-journal は呼び出し元の `main` 行（`main_row_id`）を把握しており、`envelope.candidates` の配列順に `journal` シートへ行を追記する。
- `envelope.query` は、fetch-journal が呼び出し時に渡した検索キーをそのまま返す値であり、`main_row_id` の代替ではなく、結果を呼び出し元と対応付けるためのトレーサビリティ情報として保持する。外部 adapter は `main.search_query` を優先し、空の場合のみ移行補助として `main.journal_name` を使う。`main.name` には fallback しない。SEALIB adapter は DB照合用として `main.name`、空なら `main.o_name` を使い、`search_query` / `journal_name` は使わない。
- **candidate_rank（将来拡張候補）**: 現時点では `candidate_rank` 列は採用しない。複数候補の順序は `journal` シート上の行順で十分とみなす。現行の `journal` シート（`journal_metrics.py` の `JOURNAL_HEADERS`）にも `candidate_rank` 列は存在しない。候補順位やスコア順を明示的に列として保持する必要が生じた場合のみ、将来タスクで `candidate_rank` 列の追加を検討する。

### 4.3 envelope（adapter 戻り値全体）

```
{
  "status": "<§4.4 のいずれか>",
  "source": "<取得元識別子>",
  "query": "<検索に用いたクエリ文字列>",
  "candidates": [ <candidate, ...> ],
  "error": "<adapter_error 時のメッセージ。それ以外は null>"
}
```

- `query` は実際に adapter へ渡した検索文字列。外部 adapter では `main.search_query`、空なら `main.journal_name`。SEALIB adapter では `main.name`、空なら `main.o_name`。fetch-journal が `main_row_id` と紐付けるためのトレーサビリティ用途。
- `candidates` は 0 件以上の配列。

### 4.4 status 語彙

**adapter が返す `envelope.status`**:

| 値 | 意味 |
| --- | --- |
| `fetched` | 候補が 1 件取得できた |
| `not_found` | 候補が 0 件 |
| `multiple_candidates` | 候補が 2 件以上（要レビュー） |
| `adapter_error` | 取得処理が失敗（`error` に詳細メッセージを設定） |

**adapter 外（`main.status` 等）で使う将来語彙**（adapter の出力には現れない）:

| 値 | 意味 |
| --- | --- |
| `pending` | 未取得（fetch 未実行の初期状態） |
| `confirmed` | 人がレビューし候補を確定した |
| `rejected` | 人がレビューし候補を不採用とした |

**`journal.fetch_status` への対応**（fetch-journal が `envelope.status` から決定）:

| `envelope.status` | `journal.fetch_status` |
| --- | --- |
| `fetched` | `ok` |
| `not_found` | `none` |
| `multiple_candidates` | `multiple` |
| `adapter_error` | `error` |

## 5. 入出力例

### 5.1 単一候補（`fetched`）

```json
{
  "status": "fetched",
  "source": "SINTA",
  "query": "Jurnal Ilmu Komputer dan Informasi",
  "candidates": [
    {
      "source": "SINTA",
      "external_journal_id": "12345",
      "title": "Jurnal Ilmu Komputer dan Informasi",
      "issn": "1234-5678",
      "eissn": "8765-4321",
      "publisher": "Universitas Indonesia",
      "country": "ID",
      "grade": "S1",
      "url": "https://sinta.kemdikbud.go.id/journals/profile/12345",
      "note": null
    }
  ],
  "error": null
}
```

### 5.2 複数候補（`multiple_candidates`）

```json
{
  "status": "multiple_candidates",
  "source": "SINTA",
  "query": "Jurnal Ekonomi",
  "candidates": [
    {
      "source": "SINTA",
      "external_journal_id": "22001",
      "title": "Jurnal Ekonomi dan Bisnis",
      "issn": "1111-2222",
      "eissn": null,
      "publisher": "Universitas A",
      "country": "ID",
      "grade": "S2",
      "url": "https://sinta.kemdikbud.go.id/journals/profile/22001",
      "note": null
    },
    {
      "source": "SINTA",
      "external_journal_id": "22002",
      "title": "Jurnal Ekonomi Pembangunan",
      "issn": "3333-4444",
      "eissn": "5555-6666",
      "publisher": "Universitas B",
      "country": "ID",
      "grade": "S3",
      "url": "https://sinta.kemdikbud.go.id/journals/profile/22002",
      "note": null
    }
  ],
  "error": null
}
```

### 5.3 候補なし（`not_found`）

```json
{
  "status": "not_found",
  "source": "SINTA",
  "query": "Jurnal Yang Tidak Ada",
  "candidates": [],
  "error": null
}
```

### 5.4 取得エラー（`adapter_error`）

```json
{
  "status": "adapter_error",
  "source": "SINTA",
  "query": "Jurnal Ilmu Komputer dan Informasi",
  "candidates": [],
  "error": "Connection timeout after 180s"
}
```

## 6. 非対象（本書のスコープ外）

- `journal_metrics.py` の変更（`fetch-journal` の実装）
- mock adapter / SEALIB adapter / SINTA adapter 等の実装
- 外部 CLI・DB・SEALIB・SINTA への接続

## 7. convert シートと TSV 出力（要点）

`journal` シートで確定した候補は、`convert` コマンドで `convert` シートへ変換され、`export-tsv` で TSV として出力される。adapter contract の理解に必要な範囲で要点をまとめる。

### 7.1 `CONVERT_HEADERS`（10列・順序固定）

```
main_row_id, metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note, convert_status
```

| 列 | 意味 | 生成元 |
| --- | --- | --- |
| `main_row_id` | `main` シート行へのトレーサビリティ参照（TSVには出力しない） | convert 生成時に設定 |
| `metric_source` | 指標ソース識別子（例: `SINTA`） | `journal.journal_type` |
| `metric_country` | 指標ソース側の国コード（例: `ID`） | `journal.raw_json` 内 candidate の `country`（§4.1） |
| `sealib_name` | 後段照合用の名称（主キー） | `main.name` |
| `sealib_o_name` | 後段照合用の名称（fallback） | `main.o_name` |
| `sealib_id` | SEALIB 内部レコードID 相当の補助ID | `metric_source == "SEALIB"` では `journal.external_journal_id`、それ以外では `main.id`（§4.1 注記参照） |
| `grade` | 評価/等級 | `journal.grade` |
| `url` | プロフィール/詳細ページURL | `journal.profile_url` |
| `note` | 補足情報の集約（`key=value; key=value` 形式。空値キーは含めない） | `journal.external_journal_id` / `journal.affiliation` / `main.eissn` 等 |
| `convert_status` | convert ワークフロー状態（TSVには出力しない） | source の役割と `grade` の有無から決定 |

### 7.2 変換対象と人手確認の境界

| `journal.fetch_status` | 変換可否 |
| --- | --- |
| `ok`（候補1件） | 自動変換対象 |
| `multiple`（候補複数） | 人によるレビュー（候補の絞り込み）後のみ |
| `none` / `error` | 変換しない |

### 7.3 `convert_status` と export 対象判定

| 条件 | `convert_status` | 意味 |
| --- | --- | --- |
| metrics source（`SINTA`）かつ `grade` 非空 | `ready` | TSV 出力対象 |
| metrics source（`SINTA`）かつ `grade` 空 | `hold` | grade 補完待ち |
| reference source（`SEALIB`）/ test source（`MOCK`） | `skipped` | 照合確認・テスト用。TSV 出力対象外 |
| 未知 source | `skipped` | 安全側デフォルト（ホワイトリスト外は出力しない） |

`export-tsv` は `convert_status == "ready"` の行から中央8列（`metric_source`〜`note`）をそのまま射影出力する。source の役割分類の詳細は `docs/grade-and-source-policy.md` を参照。

## 8. 関連ドキュメント

- `docs/sinta-adapter-design.md`（SINTA adapter の設計）
- `docs/grade-and-source-policy.md`（`grade` / `metric_source` の役割分類）
- `docs/workflow.md` / `docs/workflow-ja.md`（運用手順）
