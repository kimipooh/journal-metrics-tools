# SEALIB REST API v1 / OAI-PMH 2.0 整合性調査（Phase 3E）

**作成日**: 2026-06-14 | **ステータス**: 調査のみ（未実装・コード変更なし）
**基準**: sealib `seas-3.3.1`（v3.3.1, 2026-05-14）
**目的**: journal-metrics-tools が将来 `journal_metrics`（または header）を更新する場合に、既存の REST API v1 / OAI-PMH 2.0 の出力仕様・連携仕様と矛盾しないかを確認する。

---

## 1. 調査したファイル

### sealib リポジトリ
- `README.md` / `CLAUDE.md`
- `docs/architecture.md` / `docs/db-fields.md` / `docs/import-reference.md` / `CHANGELOG.md`
- `docs/journal-metrics-semi-auto-design.md`（Program 1/2 親設計）
- `docs/sealib-journal-metrics-tools-design.md`
- `seas-3.3.1/api/index.php`（REST API v1 本体）
- `seas-3.3.1/api/oai.php`（OAI-PMH 2.0 本体）
- `seas-3.3.1/api/_config.php`・`seas-3.3.1/config.inc.php`
- `seas-3.3.1/admin/import-data-ext/01-3-create-metrics-table.php`
- `seas-3.3.1/admin/import-data-ext/03-1-import-metrics-sinta.php`
- `seas-3.3.1/admin/sqlite_library_seas.db` / `sqlite_library_seas_ext.db`（`.schema journal_metrics` のみ）
- `seas-3.3.1/admin/.htaccess`

### journal-metrics-tools（本リポジトリ）
- `README.md` / `docs/rebuild-plan.md` / `docs/adapter-contract.md`
- `journal_metrics.py` / `adapters/sealib.py`

---

## 2. REST API v1: journal_metrics 出力仕様

### 2.1 エンドポイント・パラメータ（`api/index.php`）

| 操作 | 内容 |
|---|---|
| `GET /api/v1/records?include=metrics` | 一覧の各レコードに `metrics: [...]` を付与 |
| `GET /api/v1/records/{id}?include=metrics` | 単一レコードに `metrics: [...]` を付与 |
| `GET /api/v1/records/{id}?include=holdings,metrics` | `include` はカンマ区切りで複数指定可（`include_requested()`）。holdings/metrics は独立に処理されるため併用可 |
| `GET /api/v1/records?metric_source=SINTA[,OTHER]` | `header.id IN (SELECT ref_id FROM journal_metrics WHERE metric_source IN (?, ...))` で絞り込み |

`metric_source` 値は `preg_replace('/[^A-Za-z0-9_]/', '', $source)` でサニタイズ（英数字・アンダースコアのみ）。

### 2.2 結合キー（`METRICS_MATCH_KEY`）

`config.inc.php`:
```php
define("ENABLE_METRICS", "1");      // 既定: 有効
define("METRICS_MATCH_KEY", "id");  // 既定: id
```

- `METRICS_MATCH_KEY="id"`（既定）→ `journal_metrics.ref_id = header.id`（完全一致）
- `METRICS_MATCH_KEY="name"` → `journal_metrics.ref_name = header.name`（完全一致）

`metrics_enabled()` が `ENABLE_METRICS === '1'` を厳密比較するため、**`ENABLE_METRICS=0` の場合は `include=metrics` / `metric_source` 指定はエラーにならず黒子で無視される**（CHANGELOG記載どおり）。

### 2.3 公開フィールド（`format_metric()`）

```php
function format_metric(array $row): array {
    return [
        'source'      => $row['metric_source']  ?: null,
        'country'     => $row['metric_country'] ?: null,
        'grade'       => $row['grade']          ?: null,
        'url'         => $row['url']            ?: null,
        'note'        => $row['note']           ?: null,
        'imported_at' => $row['imported_at']    ?: null,
    ];
}
```

- `mid` / `ref_id` / `ref_name` は SELECT 句にも含まれず、**API レスポンスには一切出ない**（非公開）。
- `note` は API で素通り公開される唯一の自由記述フィールド。

### 2.4 metrics が無いレコードの扱い

`include=metrics` 指定時、対象レコードの `metrics` キーは**常に存在**し、0件なら `[]`（空配列）。`null` や key 欠落にはならない（`fetch_metrics_for_record()` / `attach_metrics_to_records()`）。

### 2.5 `?db=ext` / `?db=core` との関係

`api/_config.php`:
```php
define('API_DB_EXT',  dirname(__DIR__) . '/admin/sqlite_library_seas_ext.db');
define('API_DB_CORE', dirname(__DIR__) . '/admin/sqlite_library_seas.db');
```
`api/index.php`: `$db_path = (input_str('db', 10) === 'core') ? API_DB_CORE : API_DB_EXT;`（既定 `ext`）。

journal_metrics の結合・フィルタは、この**選択済みDB接続に対してそのまま実行**される（別DB参照ではない）。両 DB とも `journal_metrics` テーブルを保持（後述4章）。

### 2.6 非公開フィールド

- `header` 由来: `comment`, `creator`, `creationdate`, `renewaldate` は `format_record()` で除外（Journal Metricsとは無関係の既存仕様）。
- `journal_metrics` 由来: `mid`, `ref_id`, `ref_name` はクエリにも含まれない。

---

## 3. OAI-PMH 2.0 との関係

### 3.1 journal_metrics は出ない（意図された設計）

`api/oai.php` 全体に `journal_metrics` / `metric` / `format_metric` の参照は**0件**。`GetRecord` / `ListRecords`（`write_record()`）は `header` / `library` / `units` のみから `oai_dc`（Dublin Core）を構築している。

→ README/CHANGELOG の「v3.3.1: OAI-PMHは変更なし」と整合。**journal_metrics の更新は OAI-PMH 出力に一切影響しない**。

### 3.2 header メタ情報更新が OAI-PMH に影響するか

OAI-PMH は `header` テーブルを直接参照するため、**header 側を更新する場合は** `dc:title` や `oai:sealib...:{id}` などの識別子・メタデータが変化する。

→ journal-metrics-tools の現スコープ（`journal_metrics` への投入のみ）では無関係。ただし将来 `header` 側（例: `url`, `issn` 等）を更新する設計に拡張する場合は、OAI-PMH harvester 側のキャッシュ・差分検知に影響する点を別途検討する必要がある。

---

## 4. DB（core/ext）と公開対象の関係

### 4.1 journal_metrics テーブルの所在

`01-3-create-metrics-table.php` / `03-1-import-metrics-sinta.php` はいずれも
```php
$db_targets = array("core" => SQLITE_DATA_PATH, "ext" => SQLITE_DATA_PATH_EXT);
```
で **core/ext 両DBをループ**して同一スキーマの `journal_metrics` を作成・投入する。現状両DBとも `journal_metrics` テーブルを保持していることを `.schema` で確認済み。

```sql
CREATE TABLE IF NOT EXISTS journal_metrics (
    mid            INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_id         text,
    ref_name       text,
    metric_source  text NOT NULL,
    metric_country text,
    grade          text,
    url            text,
    note           text,
    imported_at    text
)
```
`_encode` ペアテーブルは存在しない（不要）。

### 4.2 REST API / OAI-PMH との対応

- REST API: `?db=ext`（既定）/ `?db=core` で `header`/`journal_metrics` 双方とも対象DBが切り替わる（4.1のとおり両DBに同スキーマがあるため整合）。
- OAI-PMH: `db:ext` / `db:core` セットでDB切替（`docs/architecture.md`）。journal_metrics は無関係。

### 4.3 import-data-ext の反映先

`admin/import-data-ext/`（ディレクトリ名は `-ext` だが）の `01-3` / `03-1` は **core/ext 両方** に書き込む。一方、`header`/`library` 本体の再構築は `admin/import-data/`（core用、ステップ1〜4のみ）と `admin/import-data-ext/`（拡張用、personal/NIIデータ含む）で**別系統**。journal_metrics の投入経路は core/ext 共通の単一系統である点に注意（journal-metrics-tools の convert 出力は片方のDBだけを意識する必要はない）。

---

## 5. journal-metrics-tools 側（convert / enrich-db）への影響

### 5.1 rebuild-plan.md §8 のマッピング（現行案）

| convert 列 | journal_metrics 列 | REST API 公開名 |
|---|---|---|
| `id`（=main.id, SEALIB header.id） | `ref_id` | （非公開） |
| `journal_name`（journalシートの候補名＝外部ソース表記） | `ref_name` | （非公開） |
| `journal_type` | `metric_source` | `source` |
| `grade` | `grade` | `grade` |
| `profile_url` | `url` | `url` |
| `note` | `note` | `note` |
| （列なし） | `metric_country` | `country` |
| （列なし、Program2付与） | `imported_at` | `imported_at` |

### 5.2 中心的な論点: Program 2 はどちらの方式に合わせるか

現状、`journal_metrics` への投入方式には**2つの設計**が存在する。

**(A) 現行 `03-1-import-metrics-sinta.php`（SINTA専用・実装済み）**
- TSV列: `name, id, sinta_level, sinta_url`
- `id` → `ref_id`、`name` → `ref_name` を**そのまま直接INSERT**（再解決なし）
- `metric_source='SINTA'` / `metric_country='ID'` をハードコード

**(B) `journal-metrics-semi-auto-design.md` §6 が計画する汎用 `03-2-import-metrics.php`（未実装）**
- TSV列: `metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note`
- `ref_id` は **SEALIB側名前（`sealib_name`/`sealib_o_name`）で `header` を完全一致検索して再解決**。複数候補時は `sealib_id` を補助に使用。0件は `sealib_id` 直接照合（名前不一致は警告して採用）。
- `ref_name` は TSVから受け取らず、**Program2が解決後の `header.name` を自分でセット**。

rebuild-plan §8 の現行マッピングは **(A) 方式**（`id`→`ref_id`直結、`journal_name`→`ref_name`直結）に近いが、(A) は SINTA専用ハードコードかつ「`header.id` がフルビルドで変わると `ref_id` が陳腐化する」問題を抱えている（journal-metrics-semi-auto-design.md §4.2が既に指摘）。(B) はこの問題に対応する再解決方式だが、CONVERT_HEADERS には (B) が必要とする `sealib_name` / `sealib_o_name` / `metric_country` に対応する列が無い。

→ **convert/Program2 着手前に (A) か (B) のどちらに合わせるかを確定する必要がある**（5.4「決定事項」参照）。

### 5.3 convert TSV に必要な列（現状の不足点）

1. **`metric_country`** — `journal_metrics.metric_country`（API `country`）に対応する列が CONVERT_HEADERS に無い。`adapter-contract.md` の candidate には `country` フィールドがあるが、現状 `raw_json` 内のみで journal/convertシートへの直接列がない。
   - 注意: `journal_metrics.metric_country` は SINTA側のコード系（例: `ID`=Indonesia）であり、SEALIB `header.country`（LCコード、Indonesia=`IO`）とは**別の符号系**。`adapters/sealib.py` の `--country` フィルタ（LCコード前提）と混同しないよう、convert/journal シート上で名称を区別する必要がある。
2. **SEALIB側 `name`/`o_name`**（(B)方式を採る場合） — `ref_id` 再解決の照合キーとして必要。`main.name`/`main.o_name` は MAIN_HEADERS にあるが CONVERT_HEADERS には含まれない。
3. **external_journal_id / affiliation** — `journal_metrics` に対応列なし。rebuild-plan既定は `note` へ集約。集約フォーマット（例: `"affiliation=...; external_id=..."`）の確定が必要（`note` はAPIで唯一の自由記述公開フィールドのため、フォーマットが後方互換性に影響しうる）。
4. **eissn** — `header`/`journal_metrics` いずれにも対応列なし。ツール側保持のみで確定済み（DB非同期、変更不要）。

### 5.4 enrich-db との関係

Phase 4 `enrich-db` は `main.id`/`name`/`o_name` をSEALIB DBから補完する。(B)方式を採る場合、enrich-dbで補完される `main.id`（=ある時点のheader.id）と、Program2投入時点の`header.id`がズレるリスクは依然残るが、(B)方式なら**Program2側が名前一致で再解決**するため許容範囲（(A)方式ではこのズレがそのまま`ref_id`孤立につながる）。

また、core/ext どちらのDBを enrich-db が参照するかによって `main.id` がどちらのDBの `header.id` を指すかが変わる。journal_metrics は両DB共通投入のため、(A)方式では参照元DBの選択が `ref_id` 整合性に影響する可能性がある。

---

## 6. リスク整理

| リスク | 評価 | 内容 |
|---|---|---|
| API後方互換性 | **低** | `metric_source` は文字列値の追加のみで済み、REST API・検索UIは既にソース非依存設計（`journal-metrics-semi-auto-design.md` §4.4）。スキーマ・APIコード変更は不要。 |
| OAI-PMHへの意図しない露出 | **なし** | `journal_metrics` はOAI-PMHに一切参照されない（3.1参照）。journal_metrics更新のみのスコープでは無関係。 |
| `ref_id` の不一致 | **中** | (A)方式のまま convert.id を `ref_id` に直結すると、SEALIBフルビルドで `header.id` が変わった場合に `ref_id` が孤立し、`include=metrics` で対象レコードの `metrics` が黒子で `[]` になる（エラーにはならず気付きにくい）。(B)方式（名前再解決）の採用で軽減可能。 |
| ext DB / core DB の差 | **低〜中** | `journal_metrics` は両DB共通スキーマ・共通投入経路。`header.id` がcore/ext間で一致するかは本調査では未検証（import元データは概ね共通だが要確認）。enrich-db参照DBとProgram2投入対象DBの整合に注意。 |
| メタ情報置換時の影響 | **低** | `journal_metrics` は `metric_source` 単位でDELETE→INSERTの全置換（冪等）。journal-metrics-tools はソース単位で完全な行集合をexportする前提を維持すればよい。header側の置換は本ツールのスコープ外。 |

---

## 7. まとめ

### REST API v1 の metrics 出力仕様
- `include=metrics`（`holdings`と併用可）/ `metric_source` フィルタに対応。
- 公開フィールドは `source/country/grade/url/note/imported_at` の6項目のみ（`format_metric()`）。`mid`/`ref_id`/`ref_name`は非公開。
- 結合キーは `METRICS_MATCH_KEY`（既定`id`→`ref_id=header.id`）。metricsなしは常に `[]`。
- `ENABLE_METRICS=0` でも `include=metrics`/`metric_source` はエラーにならず無視。

### OAI-PMH 2.0 との関係
- `journal_metrics` は完全に非参照。journal_metrics更新はOAI-PMH出力に影響しない（意図された設計、CHANGELOGと整合）。

### ext DB / core DB の使い分け
- `journal_metrics` は core/ext 両DBに同一スキーマで存在し、`import-data-ext`配下の投入スクリプトが両方を更新する単一系統。REST APIは`?db=`で参照先DBを切替、journal_metricsも同じ接続上で結合される。

### journal-metrics-tools 側で設計変更が必要か
**Yes（convert着手前に必要）**。rebuild-plan §8 の convert→journal_metrics マッピングは、現行の (A) SINTA専用直結方式に近いが、journal-metrics-semi-auto-design.md が計画する (B) 汎用再解決方式とは列構成が異なる。どちらに合わせるかが convert (Phase 3) のCONVERT_HEADERS確定に直結する。

### convert / enrich-db 前に決めるべき事項
1. **Program2投入方式の選択**: (A) `id`/`journal_name`を`ref_id`/`ref_name`に直結する現行03-1方式を汎用化するか、(B) `journal-metrics-semi-auto-design.md`§6の名前再解決方式（`03-2-import-metrics.php`新設）を採用するか。→ CONVERT_HEADERSの最終列構成を決定づける。
2. **`metric_country`の取得経路**: convert/journalシートに列を追加するか、export時にsource別の固定値injectとするか。SEALIB `header.country`（LCコード）とは別の符号系であることをドキュメント化。
3. **(B)採用時**: convert TSVに SEALIB側 `name`/`o_name`（再解決用照合キー）を含めるかどうか。
4. **`note`集約フォーマット**: `external_journal_id`/`affiliation`をどう`note`に集約するか（API公開唯一の自由記述フィールドのため書式を固定する必要あり）。
5. **core/ext DBの`header.id`一致性**: enrich-db参照DBとProgram2投入対象DBの組み合わせで`ref_id`不一致が生じないかの確認（本調査では未検証）。

---

## 関連ドキュメント
- `docs/rebuild-plan.md` §8（convert→journal_metricsマッピング、本調査の出発点）
- `docs/adapter-contract.md`（candidate `country`フィールドのraw_json保持）
- sealib `docs/journal-metrics-semi-auto-design.md` §4, §6（現行/計画中のjournal_metrics仕様・Program2設計）
- sealib `docs/sealib-journal-metrics-tools-design.md`
