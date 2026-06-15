# grade と metric_source の投入ポリシー（Phase 6B）

**作成日**: 2026-06-15 | **ステータス**: 設計判断（未実装・コード変更なし）
**前提**:
- `docs/convert-sheet-redesign.md`（Phase 4A、`CONVERT_HEADERS` / convert生成ルール §7）
- `docs/program2-resolution-strategy.md`（Phase 3F、(B) 名前再解決方式）
- `docs/validation-layering.md`（Phase 5A-2、`validate-tsv` 責務）
- `docs/program2-dry-run-design.md`（Phase 5A、Program2 `--dry-run` 設計）
- Phase 6A 実データ検証結果: SEALIB adapter経由のconvert行は `sealib_name`/`sealib_id` が埋まるが `grade` が空になり、`validate-tsv` がERRORになる

**対象**: `journal_metrics.py` の `generate_convert_rows`（`convert_status` 決定ロジック）、`metric_source` の分類、SEALIB adapterの位置付け

> 本書は **ポリシー整理・設計判断のみ**。`journal_metrics.py` 等のコード変更は行わない（実装はPhase 6C以降）。

---

## 0. 決定事項（要約）

- **grade はProgram2 TSVで必須のまま**。`validate-tsv` の grade空=ERROR方針は維持する。
- `metric_source` を3つの役割に分類する: **metrics source**（`SINTA`/`THAI_TIER`、Program2投入対象、grade必須）/ **reference source**（`SEALIB`、投入対象外）/ **test source**（`MOCK`、投入対象外）。
- SEALIB adapterは「SEALIB DB上のjournal検索・照合・E2Eテスト用」のreference adapterであり、`journal_metrics` へ投入するmetrics sourceではない。
- `generate_convert_rows` の `convert_status` 決定ロジックを、`fetch_status == "ok"` のみを見る現行条件から、`metric_source` の役割 + `grade` の有無を見る条件に拡張する（`ready` / `hold` / `skipped` の3値）。
- `validate-tsv` ・ `export-tsv` の既存ロジックは変更不要。`export-tsv` が `convert_status == "ready"` の行のみを出力する既存挙動により、grade空行・SEALIB/MOCK行は自然にTSVから除外される。

---

## 1. grade の扱い

### 1.1 方針: grade はProgram2 TSVで必須

`validate-tsv`（`journal_metrics.py` `validate_tsv_command`）が行う `metric_source` / `metric_country` / `grade` 非空チェック（ERROR）は**維持する**。grade空をWARNING化・任意化はしない。

### 1.2 理由

- `journal_metrics.grade` はREST API `?include=metrics` で `grade` として公開される（`docs/sealib-api-oai-compatibility-audit.md` §2.3）。`source` / `country` / `url` / `note` と並ぶ主要な公開フィールドであり、grade空のレコードを投入する実用上の意味が薄い。
- (B) 名前再解決方式（`docs/program2-resolution-strategy.md`）はProgram2投入時に `metric_source` 単位でDELETE→INSERTする。grade空行が混在すると、REST APIで「指標はあるがgradeが空」という中途半端な状態を作り出す。
- grade空は「adapterがgrade取得に未対応（SEALIBのように常時 `None`）」または「fetch時点でadapterが値を返せなかった」ことを示すシグナルである。これをエラーとして可視化し、投入前に発見できることが`validate-tsv`の価値（`docs/validation-layering.md` §1）。

---

## 2. metric_source の分類

| 役割 | metric_source例 | grade | Program2投入対象 | 用途 |
| --- | --- | --- | --- | --- |
| **metrics source** | `SINTA`, `THAI_TIER`（いずれも未実装） | adapterが必ず設定する想定 | ○ | 本番指標投入（journal_metrics REST API公開対象） |
| **reference source** | `SEALIB` | 常に空（`adapters/sealib.py` `_candidate()` L31で`grade: None`固定） | × | header照合・sealib_id確認・E2Eテスト |
| **test source** | `MOCK` | ダミー値（`"Mock Grade"`等、`adapters/mock.py`） | × | ユニット/結合テスト専用 |

### 2.1 metrics source（SINTA / THAI_TIER）

`journal_metrics` へ投入する実指標を提供するadapter。`grade` / `url` / `note` 等が実データとして埋まることが前提。現時点では未実装（README「Current commands (Phase 3D)」は`mock`/`sealib`のみ）。実装時はgradeを必ず設定する契約とする（adapter contract側の要件は別タスクで整理）。

### 2.2 reference source（SEALIB）

SEALIB DB（`header`テーブル）に対する検索・照合用adapter。`adapters/sealib.py` は `grade` / `url` / `eissn` / `publisher` を常に `None` で返す（L28-32）。`journal_metrics` テーブルへの投入価値を持つ指標データを提供しない。

### 2.3 test source（MOCK）

`adapters/mock.py` はテスト専用の固定レスポンス（`"Mock Grade"`, `"https://example.invalid/..."`等）を返す。本番投入対象外。

---

## 3. SEALIB adapter の位置付け

### 3.1 何のためのadapterか

`adapters/sealib.py` は、SEALIB SQLite DB（`header`テーブル）を `mode=ro` で検索し、`main.name` / `o_name` に一致する既存journalを候補として返す。主目的:

1. `main`シートの `name` / `o_name` がSEALIB DB上の `header.name` / `o_name` と一致するかの確認（`journal.fetch_status` がok/multiple/noneのいずれになるかの実データ検証）。
2. `sealib_id`（`header.id`）をconvert行へ補完するための参照情報取得。
3. fetch-journal → convert → export-tsv → validate-tsv パイプライン全体を、SINTA/THAI_TIER実装前に実データで通すE2Eテスト。

### 3.2 metrics sourceではない

`journal_metrics` に投入する `grade` / `url` / `note` 等のペイロードを持たない（§2.2）。`convert.sealib_name` / `sealib_o_name` / `sealib_id` はProgram2の**照合キー**であり、`sealib_name` / `sealib_o_name` は常に `main.name` / `main.o_name` から補完する。`sealib_id` は SEALIB `header.id` の補助値で、SEALIB adapter行では `journal.external_journal_id`（=`header.id`）、外部 metrics source行では `main.id` から補完する。SINTA `journal_id` 等の外部IDは `note.external_id` に集約し、`sealib_id` には入れない。SEALIB adapterで取得した `external_journal_id`（=`header.id`）は `sealib_id` の補完に使えるが、それは「SEALIB行をProgram2投入対象にする理由」にはならない。

### 3.3 convert_statusをreadyにすべきか

結論: **すべきでない**。`journal_type=="SEALIB"` の journal 行から生成されるconvert行は、`convert_status` を `ready` にしない（§4で `skipped` に分類）。ただし、convert行自体は生成し、`sealib_name` / `sealib_o_name` / `sealib_id` の解決結果を確認できる状態で残す（トレーサビリティ・デバッグ用）。`skipped` 行はexport-tsvで自然に除外される。

---

## 4. convert生成ルールへの影響

### 4.1 現行ロジック（`journal_metrics.py` `generate_convert_rows`）

```python
if text_value(journal_row.get("fetch_status")).lower() != "ok":
    return None
...
return {..., "convert_status": "ready"}
```

`fetch_status == "ok"` のみを見て無条件に `convert_status="ready"` を設定する。`metric_source` の値や `grade` の有無は見ていない。

### 4.2 Phase 6A で判明した問題

- `journal_type=="SEALIB"`（reference source）の行は `grade` が常に空（§2.2）。
- 現行ロジックでは `fetch_status=="ok"` であれば `convert_status="ready"` になり、`export-tsv` でTSVに出力される。
- 出力されたTSVは `validate-tsv` の `grade` 必須チェックでERRORになる。

### 4.3 新ルール案

`convert_status` を以下の3値で決定する（`ready` / `hold` / `skipped`。`exported` / `imported` は `export-tsv` 以降で付与される既存の状態のまま）。

| 条件 | `convert_status` | 意味 |
| --- | --- | --- |
| `fetch_status != "ok"` | （convert行を生成しない・現行どおり） | 候補未確定 |
| `metric_source` が **reference/test source**（`SEALIB`, `MOCK`） | `skipped` | Program2投入対象外。照合キー確認・テスト用として行は残す |
| `metric_source` が **metrics source**（`SINTA`, `THAI_TIER`）かつ `grade` が空 | `hold` | 投入対象だがgrade欠落。adapter側の再取得・補完待ち |
| `metric_source` が **metrics source** かつ `grade` が非空 | `ready` | Program2投入対象 |
| `metric_source` が上記いずれにも分類されない未知の値 | `skipped` | 安全側デフォルト（ホワイトリスト外は投入しない） |

### 4.4 hold行の再評価

`convert` コマンドは実行毎に `convert` シートを再生成する（`reset_convert_sheet`）。`fetch-journal` 再実行（再取得）で `journal.grade` が補完されれば、次回 `convert` 実行時に同じ行が `hold` → `ready` へ自然に遷移する。追加の状態遷移処理は不要。

---

## 5. validate-tsv との関係

- `validate-tsv` の `metric_source` / `metric_country` / `grade` 非空チェック（ERROR）は**変更しない**。
- `export-tsv` は `convert_status == "ready"` の行のみを出力する既存ロジック（`journal_metrics.py` L479）を**変更しない**。
- §4.3のとおり `ready` は「metrics sourceかつgrade非空」の場合のみ付与されるため、`export-tsv` の出力行は常に `grade` 非空・`metric_source` がmetrics sourceとなり、`validate-tsv` のERROR条件に該当しなくなる。
- つまり、Phase 6A の問題は `validate-tsv` 側ではなく `generate_convert_rows` の `convert_status` 決定ロジック側で解消する。

---

## 6. Phase 6C 実装候補（最小実装）

1. `journal_metrics.py` に `metric_source` 役割定義を追加（例: `METRICS_SOURCE_TYPES = {"SINTA", "THAI_TIER"}`、`REFERENCE_SOURCE_TYPES = {"SEALIB"}`、`TEST_SOURCE_TYPES = {"MOCK"}`、またはひとつの役割mapping辞書）。
2. `generate_convert_rows` の `convert_status` 決定部分を §4.3 のルールに置き換える（`"ready"` 固定 → 条件分岐）。
3. `export-tsv` / `validate-tsv` / `CONVERT_HEADERS` / `PROGRAM2_TSV_HEADERS` はロジック変更不要（§5）。
4. 単体テスト追加:
   - `journal_type=="SEALIB"`, `fetch_status=="ok"` → `convert_status=="skipped"`
   - `journal_type=="MOCK"`, `fetch_status=="ok"` → `convert_status=="skipped"`
   - `metric_source` がmetrics source、`grade` 空 → `convert_status=="hold"`
   - `metric_source` がmetrics source、`grade` 非空 → `convert_status=="ready"`
5. `docs/convert-sheet-redesign.md` §7（`journal`→`convert` 生成ルール表）・`convert_status` 語彙（`ready`/`exported`/`imported`/`skipped`/`hold`）の更新（ドキュメント整合性。Phase 6Cで実施）。

---

## 7. 非対象（本フェーズで行わないこと）

- SINTA adapter / Thai Tier adapter の実装
- grade値の正規化（legacy `metrics_excel.py` の正規化ロジックの新CLIへの移植）
- Program2（`03-2-import-metrics.php`）の変更
- SEALIB DBへの書き込み
- 本番データの投入
- `journal_metrics.py` 等のコード変更（Phase 6Cで実施）

---

## 関連ドキュメント

- `docs/convert-sheet-redesign.md`（Phase 4A。`CONVERT_HEADERS` ・convert生成ルール §7 ・`convert_status` 語彙）
- `docs/program2-resolution-strategy.md`（Phase 3F。(B) 名前再解決方式）
- `docs/validation-layering.md`（Phase 5A-2。`validate-tsv` 責務）
- `docs/program2-dry-run-design.md`（Phase 5A。Program2 `--dry-run` 設計）
- `journal_metrics.py`（`generate_convert_rows`, `validate_tsv_command`, `PROGRAM2_TSV_HEADERS`, `CONVERT_HEADERS`）
- `adapters/sealib.py`（`_candidate()` L14-34、`grade: None` 固定）
- `adapters/mock.py`（test source固定値）
