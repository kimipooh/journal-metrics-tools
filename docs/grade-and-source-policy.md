# grade と metric_source の投入ポリシー

**作成日**: 2026-06-15 | **ステータス**: 設計判断（v1.0.0 で実装済み）

**対象**: `journal_metrics.py` の `generate_convert_rows`（`convert_status` 決定ロジック）、`metric_source` の分類、SEALIB adapterの位置付け

> **v1.0.0 注記**: 実装済み adapter は `mock` / `sealib` / `sinta` のみ。現行実装は `journal_metrics.py` / `journal_mapper.py` / `adapters/` である。

---

## 0. 決定事項（要約）

- **grade は export TSV で必須のまま**。`validate-tsv` の grade空=ERROR方針は維持する。
- `metric_source` を3つの役割に分類する: **metrics source**（`SINTA`、export TSV 出力対象、grade必須）/ **reference source**（`SEALIB`、出力対象外）/ **test source**（`MOCK`、出力対象外）。
- SEALIB adapterは「SEALIB DB上のjournal検索・照合・E2Eテスト用」のreference adapterであり、後段 import へ投入するmetrics sourceではない。
- `generate_convert_rows` の `convert_status` 決定ロジックは、`fetch_status == "ok"` のみを見る条件ではなく、`metric_source` の役割 + `grade` の有無を見る条件とする（`ready` / `hold` / `skipped` の3値）。
- `validate-tsv` ・ `export-tsv` の既存ロジックは変更不要。`export-tsv` が `convert_status == "ready"` の行のみを出力する挙動により、grade空行・SEALIB/MOCK行は自然にTSVから除外される。

---

## 1. grade の扱い

### 1.1 方針: grade は export TSV で必須

`validate-tsv`（`journal_metrics.py` `validate_tsv_command`）が行う `metric_source` / `metric_country` / `grade` 非空チェック（ERROR）は**維持する**。grade空をWARNING化・任意化はしない。

### 1.2 理由

- `grade` は `source` / `country` / `url` / `note` と並ぶ主要フィールドであり、後段システムでもそのまま公開・利用されることを想定する。grade空のレコードを投入する実用上の意味が薄い。
- 後段の import 処理が `metric_source` 単位で指標を置換更新する運用を想定すると、grade空行が混在した場合に「指標はあるがgradeが空」という中途半端な状態を作り出す。
- grade空は「adapterがgrade取得に未対応（SEALIBのように常時 `None`）」または「fetch時点でadapterが値を返せなかった」ことを示すシグナルである。これをエラーとして可視化し、投入前に発見できることが`validate-tsv`の価値である。

---

## 2. metric_source の分類

| 役割 | metric_source例 | grade | export TSV 出力対象 | 用途 |
| --- | --- | --- | --- | --- |
| **metrics source** | `SINTA` | adapterが必ず設定する想定 | ○ | 外部評価指標の投入用データ（後段 import 対象） |
| **reference source** | `SEALIB` | 常に空（`adapters/sealib.py` `_candidate()` で`grade: None`固定） | × | 照合・sealib_id確認・E2Eテスト |
| **test source** | `MOCK` | ダミー値（`"Mock Grade"`等、`adapters/mock.py`） | × | ユニット/結合テスト専用 |

### 2.1 metrics source（SINTA）

後段へ投入する実指標を提供するadapter。`grade` / `url` / `note` 等が実データとして埋まることが前提。v1.0.0 時点では `sinta` adapter が該当する。実装時はgradeを必ず設定する契約とする（adapter contract側の要件は別タスクで整理）。

### 2.2 reference source（SEALIB）

SEALIB DB（`header`テーブル）に対する検索・照合用adapter。`adapters/sealib.py` は `grade` / `url` / `eissn` / `publisher` を常に `None` で返す。後段へ投入する価値を持つ指標データを提供しない。

### 2.3 test source（MOCK）

`adapters/mock.py` はテスト専用の固定レスポンス（`"Mock Grade"`, `"https://example.invalid/..."`等）を返す。投入対象外。

---

## 3. SEALIB adapter の位置付け

### 3.1 何のためのadapterか

`adapters/sealib.py` は、SEALIB SQLite DB（`header`テーブル）を `mode=ro` で検索し、`main.name` / `o_name` に一致する既存journalを候補として返す。主目的:

1. `main`シートの `name` / `o_name` がSEALIB DB上の `header.name` / `o_name` と一致するかの確認（`journal.fetch_status` がok/multiple/noneのいずれになるかの実データ検証）。
2. `sealib_id`（`header.id`）をconvert行へ補完するための参照情報取得。
3. fetch-journal → convert → export-tsv → validate-tsv パイプライン全体を、metrics source 実データの投入前に通すE2Eテスト。

### 3.2 metrics sourceではない

後段へ投入する `grade` / `url` / `note` 等のペイロードを持たない（§2.2）。`convert.sealib_name` / `sealib_o_name` / `sealib_id` は後段 import での**照合キー**であり、`sealib_name` / `sealib_o_name` は常に `main.name` / `main.o_name` から補完する。`sealib_id` は SEALIB `header.id` の補助値で、SEALIB adapter行では `journal.external_journal_id`（=`header.id`）、外部 metrics source行では `main.id` から補完する。SINTA `journal_id` 等の外部IDは `note.external_id` に集約し、`sealib_id` には入れない。SEALIB adapterで取得した `external_journal_id`（=`header.id`）は `sealib_id` の補完に使えるが、それは「SEALIB行を export 対象にする理由」にはならない。

### 3.3 convert_statusをreadyにすべきか

結論: **すべきでない**。`journal_type=="SEALIB"` の journal 行から生成されるconvert行は、`convert_status` を `ready` にしない（§4で `skipped` に分類）。ただし、convert行自体は生成し、`sealib_name` / `sealib_o_name` / `sealib_id` の解決結果を確認できる状態で残す（トレーサビリティ・デバッグ用）。`skipped` 行はexport-tsvで自然に除外される。

---

## 4. convert生成ルールへの影響

### 4.1 変更前のロジック（`journal_metrics.py` `generate_convert_rows`）

```python
if text_value(journal_row.get("fetch_status")).lower() != "ok":
    return None
...
return {..., "convert_status": "ready"}
```

`fetch_status == "ok"` のみを見て無条件に `convert_status="ready"` を設定していた。`metric_source` の値や `grade` の有無は見ていない。

### 4.2 変更前のロジックで生じる問題

- `journal_type=="SEALIB"`（reference source）の行は `grade` が常に空（§2.2）。
- 変更前のロジックでは `fetch_status=="ok"` であれば `convert_status="ready"` になり、`export-tsv` でTSVに出力される。
- 出力されたTSVは `validate-tsv` の `grade` 必須チェックでERRORになる。

### 4.3 新ルール

`convert_status` を以下の3値で決定する（`ready` / `hold` / `skipped`。`exported` / `imported` は `export-tsv` 以降で付与される将来語彙）。

| 条件 | `convert_status` | 意味 |
| --- | --- | --- |
| `fetch_status != "ok"` | （convert行を生成しない・従来どおり） | 候補未確定 |
| `metric_source` が **reference/test source**（`SEALIB`, `MOCK`） | `skipped` | export 対象外。照合キー確認・テスト用として行は残す |
| `metric_source` が **metrics source**（`SINTA`）かつ `grade` が空 | `hold` | 投入対象だがgrade欠落。adapter側の再取得・補完待ち |
| `metric_source` が **metrics source** かつ `grade` が非空 | `ready` | export TSV 出力対象 |
| `metric_source` が上記いずれにも分類されない未知の値 | `skipped` | 安全側デフォルト（ホワイトリスト外は投入しない） |

### 4.4 hold行の再評価

`convert` コマンドは実行毎に `convert` シートを再生成する（`reset_convert_sheet`）。`fetch-journal` 再実行（再取得）で `journal.grade` が補完されれば、次回 `convert` 実行時に同じ行が `hold` → `ready` へ自然に遷移する。追加の状態遷移処理は不要。

---

## 5. validate-tsv との関係

- `validate-tsv` の `metric_source` / `metric_country` / `grade` 非空チェック（ERROR）は**変更しない**。
- `export-tsv` は `convert_status == "ready"` の行のみを出力する既存ロジックを**変更しない**。
- §4.3のとおり `ready` は「metrics sourceかつgrade非空」の場合のみ付与されるため、`export-tsv` の出力行は常に `grade` 非空・`metric_source` がmetrics sourceとなり、`validate-tsv` のERROR条件に該当しなくなる。
- つまり、§4.2 の問題は `validate-tsv` 側ではなく `generate_convert_rows` の `convert_status` 決定ロジック側で解消する。

---

## 6. 実装内容（最小実装）

1. `journal_metrics.py` に `metric_source` 役割定義を追加（例: `METRICS_SOURCE_TYPES = {"SINTA"}`、`REFERENCE_SOURCE_TYPES = {"SEALIB"}`、`TEST_SOURCE_TYPES = {"MOCK"}`、またはひとつの役割mapping辞書）。
2. `generate_convert_rows` の `convert_status` 決定部分を §4.3 のルールに置き換える（`"ready"` 固定 → 条件分岐）。
3. `export-tsv` / `validate-tsv` / `CONVERT_HEADERS` / `PROGRAM2_TSV_HEADERS` はロジック変更不要（§5）。
4. 単体テスト追加:
   - `journal_type=="SEALIB"`, `fetch_status=="ok"` → `convert_status=="skipped"`
   - `journal_type=="MOCK"`, `fetch_status=="ok"` → `convert_status=="skipped"`
   - `metric_source` がmetrics source、`grade` 空 → `convert_status=="hold"`
   - `metric_source` がmetrics source、`grade` 非空 → `convert_status=="ready"`

---

## 7. 非対象（本書で扱わないこと）

- SINTA adapter の追加拡張
- grade値の正規化
- 後段 import ツールの変更
- SEALIB DBへの書き込み
- 本番データの投入

---

## 関連ドキュメント

- `docs/adapter-contract.md`（candidate / envelope / status 語彙の共通契約、convert シートと TSV 出力の要点）
- `journal_metrics.py`（`generate_convert_rows`, `validate_tsv_command`, `PROGRAM2_TSV_HEADERS`, `CONVERT_HEADERS`）
- `adapters/sealib.py`（`_candidate()`、`grade: None` 固定）
- `adapters/mock.py`（test source固定値）
