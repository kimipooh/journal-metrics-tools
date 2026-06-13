# Adapter Contract（Journal Metrics 取得アダプタ共通仕様）

> 本書は **contract 定義のみ**。実装は対象外（Phase 2B 以降）。journal_metrics.py / metrics_excel.py への変更は含まない。

## 1. 目的

`fetch-journal`（Phase 2）は、外部ソース（SINTA / Thai Tier / SEALIB / 将来のソース）から Journal Metrics 候補を取得し、`journal` シートへ書き込む。本書は、その「取得」を担う **adapter** が満たすべき共通 contract（入出力形式・フィールド定義・status 語彙）を定義する。

adapter contract を固定することで、ソースごとの差異を adapter 内部に閉じ込め、`journal_metrics.py` 側（Excel 書き込み層）はソースを問わず同じ形式を扱える。

## 2. レイヤー分離

| レイヤー | 責務 | 実装時期 |
| --- | --- | --- |
| **adapter（外部ソース取得層）** | 検索クエリを受け取り、本書 §4 の共通形式（envelope + candidates）で結果を返す。ソース固有のスクレイピング/API呼び出し/DB読み取りはここに閉じる。 | Phase 2B（mock）/ Phase 2C 以降（実ソース） |
| **fetch-journal（Excel 書き込み層）** | main の対象行ごとに adapter を呼び出し、envelope を `journal` シートへ書き込む。`fetch_status` 決定、`grade` のソース横断正規化、`raw_json` 保存、`fetched_at` 設定を行う。 | Phase 2 以降（本書はスコープ外） |

adapter は **Excel I/O を行わない**。`journal_metrics.py` は **ソース固有ロジックを持たない**。

## 3. 対応ソースと実装方針

adapter contract は SEALIB / SINTA / Thai Tier / 将来ソースのいずれであっても同一の共通形式（§4）で結果を返す。adapter は各ソース固有の取得結果を共通フィールドへマッピングする。`grade` はソース表記の raw 値のまま返し、adapter は正規化を行わない（grade のソース横断正規化は fetch-journal 側 §2 の責務）。対応するフィールドが無いソースについては、当該フィールドを `null` として返すことで差異を吸収する。

- **Phase 2B**: 外部接続を行わない **mock adapter** を実装し、本 contract に準拠した固定/サンプル候補を返す。fetch-journal の実装・テストに先行して contract を検証する。
- **Phase 2C 以降**: 実ソース adapter を実装する。**SEALIB adapter** を含む（SEALIB 側の既存メトリクスデータを Journal Metrics ソースの一つとして読み取る用途を想定）。SINTA / Thai Tier 等の外部 CLI 経由 adapter も同方針で追加する。
- 実装方式（in-process 関数 / 外部 CLI subprocess 等）は Phase 2B/2C で個別に確定する。本書は **入出力形式のみ** を固定する。

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
| `source` | 取得元識別子（`SINTA` / `THAI_TIER` / `SEALIB` 等） | **必須** | 空値不可 | `journal_type` |
| `external_journal_id` | ソース側の journal ID | 任意 | 不明時は `null`（Excel では空セル） | `external_journal_id` |
| `title` | 候補の名称（ソース表記） | **必須**（候補が存在する限り必須） | 空値不可 | `journal_name` |
| `issn` | Print ISSN | 任意 | 不明時は `null` | 直接対応列なし → `raw_json` に保持 |
| `eissn` | Electronic ISSN | 任意 | 不明時は `null` | 直接対応列なし → `raw_json` に保持 |
| `publisher` | 発行者/所属機関 | 任意 | 不明時は `null` | `affiliation`（既存列を再利用。「発行者」と「所属機関」の意味差はあるが、現状最も近い既存列として割当。差異が問題化した場合は別タスクで再検討） |
| `country` | 国/地域コード | 任意 | 不明時は `null` | 直接対応列なし → `raw_json` に保持 |
| `grade` | ソース表記の評価・等級（**正規化前の raw 値**） | 任意 | 対象外/不明時は `null` | `grade`（fetch-journal 側で `journal_type` 別の正規化を適用してから書き込む。adapter は正規化しない） |
| `url` | プロフィール/詳細ページ URL | 任意 | 不明時は `null` | `profile_url` |
| `note` | adapter からの補足情報（自由記述） | 任意 | 不明時は `null` | 直接対応列なし → `raw_json` に保持（`journal.note` 列の追加は本書スコープ外の将来検討事項） |

- JSON 上の空値は **`null`** を用いる（`""` ではない）。
- `journal.raw_json` には **candidate オブジェクト全体**（上記フィールドすべて）を JSON 文字列として保存する。直接対応列がないフィールド（`issn`/`eissn`/`country`/`note`）はこの `raw_json` 経由でのみ保持される。

### 4.2 候補と journal 行の対応関係（main_row_id）

- **1 candidate = 1 `journal` シート行**。1 件の `main` 行に対し、`fetch-journal` は 0 件以上の candidate を `journal` シートへ複数行として書き込む（1:N）。
- `journal.main_row_id` で `main` 行と紐づける。複数候補が存在する場合は、同一 `main_row_id` を持つ `journal` シート上の行順で `envelope.candidates` 配列内の順序を保持する。
- **adapter の candidate オブジェクト（§4.1）には `main_row_id` を含めない**。adapter は呼び出し元の `main` 行を意識しない。
- `main_row_id` は **fetch-journal（Excel 書き込み層）が付与する**。fetch-journal は呼び出し元の `main` 行（`main_row_id`）を把握しており、`envelope.candidates` の配列順に `journal` シートへ行を追記する。
- `envelope.query` は、fetch-journal が呼び出し時に渡した検索キーをそのまま返す値であり、`main_row_id` の代替ではなく、結果を呼び出し元と対応付けるためのトレーサビリティ情報として保持する。
- **candidate_rank（将来拡張候補）**: 現時点では `candidate_rank` 列は採用しない。複数候補の順序は `journal` シート上の行順で十分とみなす。Phase 1 の `journal` シート（`journal_metrics.py` の `JOURNAL_HEADERS`）にも `candidate_rank` 列は存在しない。候補順位やスコア順を明示的に列として保持する必要が生じた場合のみ、将来タスクで `candidate_rank` 列の追加を検討する。

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

- `query` は通常 `main.journal_name`（空なら `main.name`）。fetch-journal が `main_row_id` と紐付けるためのトレーサビリティ用途。
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
- 旧 `metrics_excel.py` の変更

## 7. 関連ドキュメント

- `docs/rebuild-plan.md` §7 アダプタ contract（fetch-journal / enrich-db 共通の考え方）
- `.codex/tasks/phase1-journal-metrics-template.md`（`journal` シートヘッダ定義の根拠）
- `README.md`（現行 Phase 状況）
