# journal-metrics-tools 再構築計画（rebuild-plan）

> 本書は **設計メモ** であり、コード変更を含まない。実装は本書の Phase 計画に従い、CLAUDE.md 規約のもと Codex へ引き継ぐ。

## 0. 方針サマリ

- **段階的移行ではなく、完全再設計・再実装**を行う。
- 旧 `metrics_excel.py`（SEALIB/SINTA 2 シート方式）は **legacy reference として扱い**、拡張しない。
- 新メイン CLI は **`journal_metrics.py`** とし、**`template` コマンドから最小実装で作り直す**。
- 旧 `init` / `fetch` / `refresh` / `export` / `report` / `import-existing-master` の **互換維持は優先しない**。
- 旧実装からは **再利用できる「考え方」のみ抽出**する（adapter 呼び出し / grade 正規化 / Excel 保存 / read-only DB / status 駆動）。
- Phase 計画: **1) `template` → 2) `fetch-journal` → 3) `convert` → 4) `enrich-db`**。

## 0.1. 命名方針

- 今後の新実装のメイン CLI 名は **`journal_metrics.py`** に統一する。
- 旧 `metrics_excel.py` は **legacy reference** として扱い、直接改造しない。
- 旧 `metrics_excel.py` の移動・削除は本計画メモ上の別タスク候補に留め、Phase 1 の最小実装では新規 `journal_metrics.py` の作成を優先する。
- ドキュメント上で `metrics_excel.py` と記す場合は、旧実装・旧運用・legacy reference の説明に限定する。

## 1. 背景

本ツールは独立した**汎用 Journal Metrics 収集・確認・変換ツール**を目指す。SEALIB は利用先の一つに過ぎず、将来 SINTA / Thai Tier / 他ソースを扱う。

旧 `metrics_excel.py` は次の点で汎用ツールに不適:

1. **DB ダンプ的** — `init` が SEALIB `header` をそのまま展開（`init_command` `metrics_excel.py:268-312`）。入力フォームでない。
2. **SEALIB 強結合** — `sealib_*` 列名（`MAP_HEADERS` `:43-59`）、`--db-path` 必須、`COUNTRY_ALIASES = {"ID":"IO"}`（`:72-74`）、`header` テーブル固定。
3. **SINTA 固有** — raw 列が SINTA 形状（`RAW_HEADERS` `:23-31`）。`journal_type` 概念がなく、複数ソース混在不可。
4. **制御列の過負荷** — `confirmed`(0/1) と `status`(enum) の二重管理、死に列 `garuda_name`。

→ 互換を保ったまま改造するより、**3 シート（main / journal / convert）構成で作り直す**方が筋が良い。

## 2. 旧実装の位置づけ（legacy reference）

- **退避先（案）**: 将来必要になれば `legacy/metrics_excel.py` へ移動し、ファイル先頭に「LEGACY REFERENCE — 参考凍結。拡張しない」注記を付す。
- 退避は **Phase 1 の最小実装には含めず、別タスク化**する（本メモではコード変更しない）。
- 新 `journal_metrics.py` を **空から最小構成で新規作成**する。
- README / CHANGELOG の該当箇所は legacy 注記へ更新（Phase 1 のドキュメント整合作業に含める）。
- 旧 2 シート Excel の既存運用が必要な間は、旧 `metrics_excel.py` を legacy ツールとしてそのまま実行できる状態を保つ（新ツールへの取り込みは互換優先しないため、必要になった時点で別タスク化）。

## 3. 旧実装から抽出する「再利用できる考え方」

新規実装でも踏襲する設計思想。**コードのコピーではなく考え方の流用**を基本とする。

| 概念 | 旧該当（file:line） | 新での扱い |
| --- | --- | --- |
| **Excel ヘルパ群** | `load_or_create_workbook` / `ensure_sheet(wb, title, headers)` / `get_value(ws, row, 列名)` / `row_has_content`（`:244-245`）/ `now_text`（`:93-94`） | **ヘッダ名ベースのセルアクセス**を新 3 シートでも踏襲。列順変更に強い設計を維持 |
| **adapter 呼び出し** | `resolve_adapter_command`（`:97-132`）: `--adapter-command`（スクリプトパス）+ `--python`（インタプリタ）を分離、`shlex.split`、スクリプト存在検証、`subprocess` 実行 + JSON parse | `fetch-journal` の **adapter contract** に流用。`journal_type` 別にアダプタを差し替え可能に一般化 |
| **grade 正規化** | `normalized_grade()`（`export_command` `:617` で使用、`(grade, warning)` を返す。例: `S1` → `S1 Accredited`、未知値は警告） | `journal.grade` の正規化に流用。**`journal_type` 別の正規化テーブル**へ一般化（SINTA / Thai Tier で別ルール） |
| **read-only DB アクセス** | `read_sealib_rows`（`:248-265`）: `sqlite3` URI `?mode=ro`、`quote()` でパス安全化、`row_factory=Row` | `enrich-db` の **DB adapter** に流用。**read-only 厳守**（ツールは DB へ書かない） |
| **status 駆動の対象抽出** | `init` が `needs_fetch` を付与（`:290`）、`fetch` が 1 件=確定 / 0・2 件以上=要レビュー / 失敗=エラーで分岐 | `main.status` / `journal.fetch_status` に流用。**語彙は刷新**（§4 参照） |
| **列エイリアス取り込み** | `LEGACY_MAP_COLUMNS`（`:79-90`） | 将来 legacy Excel を取り込む必要が出た場合の参照。**今は不要**（互換優先しない） |

> `sheet_names(source, country)`（`:135`〜、`ID（SINTAツール分析）` 等の動的シート名）は **流用しない**。新設計はシート名を固定（`main` / `journal` / `convert`）し、`source`/`country` 相当は列（`journal_type` / `metric_country`）へ移す。

## 4. 新 3 シート構成

```
main (人が編集する入力フォーム)
   │  fetch-journal（外部アダプタ: SINTA / Thai Tier / …）
   ▼
journal (外部ツール収集結果・監査ログ 1:N)
   │  人が確定（採用候補の選択）
   ▼
convert (DB 投入用・確定行)
   │  convert → TSV / SQL
   ▼
SEALIB 等（取込は SEALIB 側 import-data-ext が実施）
```

**main**（人が編集する主シート）

| 列 | 意味 |
| --- | --- |
| `id` | DB 側 ID（空可。手動作成可、後で `enrich-db` 補完） |
| `name` | 名称 |
| `o_name` | 原語名 |
| `issn` | ISSN |
| `eissn` | eISSN（新規。SEALIB `header` に列なし→ツール側保持のみ、DB へは同期しない） |
| `journal_name` | 外部ツール検索キー |
| `note` | 備考 |
| `status` | 進捗（単一列。語彙案: `new` / `queued` / `fetched` / `reviewed` / `converted` / `hold`） |

**journal**（外部ツール取得結果）

| 列 | 意味 |
| --- | --- |
| `main_row_id` | main 行への参照 |
| `journal_name` | 取得名称 |
| `journal_type` | ソース種別 `SINTA` / `THAI_TIER` …（新規） |
| `grade` | 正規化グレード（`journal_type` 別ルール） |
| `affiliation` | 所属 |
| `external_journal_id` | 外部 ID |
| `profile_url` | プロフィール URL |
| `raw_json` | アダプタ生出力（新規。detail 系の細目はここへ集約） |
| `fetched_at` | 取得時刻 |
| `fetch_status` | `ok` / `multiple` / `none` / `error` |

**convert**（DB 投入用）

| 列 | 意味 |
| --- | --- |
| `id` | DB 側 ID（match key） |
| `journal_type` | ソース種別 |
| `grade` | グレード |
| `external_journal_id` | 外部 ID |
| `profile_url` | URL |
| `journal_name` | 名称 |
| `affiliation` | 所属 |
| `note` | 備考 |
| `convert_status` | `ready` / `exported` / `imported` / `skipped` |

## 5. 新コマンド体系（最小実装で段階構築）

| コマンド | Phase | 役割 | 主な I/O |
| --- | --- | --- | --- |
| `template` | 1 | 空の main/journal/convert/README ワークブック生成。**DB 不要**の汎用ブートストラップ | `--output` → 4 シート + ヘッダ/説明行 |
| `fetch-journal` | 2 | main の `status` から対象抽出 → アダプタ呼び出し → journal へ候補追記 | `--xlsx` `--adapter-command` `--python` `--journal-type` → `journal` シート更新 |
| `convert` | 3 | 確定した main↔journal 選択から convert 行生成 + DB 投入物出力 | `--xlsx` `--out`（TSV/SQL） → `convert` シート + 出力ファイル |
| `enrich-db` | 4 | main の `id`/`name`/`o_name` から **DB adapter 経由**で欠損列補完 | `--xlsx` `--db-path`（任意） → `main` シート補完 |

- 互換用の旧コマンドは新ツールに実装しない（必要なら旧 `metrics_excel.py` を legacy ツールとして使う）。
- `refresh` / `report` 相当は将来必要になれば `fetch-journal --refresh` / `report` として追加（本計画のスコープ外）。

## 6. Phase 計画

各 Phase は **最小実装 → レビュー → 次へ**。実装は Codex 引き継ぎ（`.codex/tasks/task-YYYYMMDD-HHMM.md`）。

### Phase 1 — `template`（最小の足場）
- 旧 `metrics_excel.py` は legacy reference として参照のみ行い、直接改造・移動・削除しない。
- 新 `journal_metrics.py` を新規作成。Excel ヘルパ群（§3）の考え方を必要最小限で反映する。
- `template` コマンドで main/journal/convert/README の 4 シート + ヘッダを生成。
- 依存は `openpyxl` のみ（旧と同じ）。
- **検証**: `python journal_metrics.py template --output out.xlsx` → 4 シート・正しいヘッダ・説明行で生成されること。

### Phase 2 — `fetch-journal`
- **adapter contract** を確定（§7）。`resolve_adapter_command` の考え方を流用。
- main の対象行（`status`）ごとにアダプタ呼び出し → 候補を journal シートへ。
- `journal_type` 付与、`grade` 正規化（`journal_type` 別）、`raw_json` 保存、`fetch_status` 設定。
- **検証**: SINTA アダプタ（`../sinta-full-cli-v3/sinta-full-cli-v3.py`）で実 journal シートが生成され、1/複数/0/エラーが `fetch_status` に反映されること。

### Phase 3 — `convert`
- main↔journal の確定（採用候補選択）から convert 行を生成。`convert_status` でゲート。
- TSV/SQL を出力（DB 投入物）。grade 正規化を再利用。
- **検証**: convert シート + TSV が生成され、確定行のみ含まれること。SEALIB `journal_metrics` へのマッピング（§8）が成立すること。

### Phase 4 — `enrich-db`
- DB adapter（`SEALIBAdapter`）を実装。`read_sealib_rows` の read-only 方式を流用。
- main の `id`/`name`/`o_name` のいずれかをキーに欠損列を補完。
- **位置付け（Phase 3F）**: `enrich-db` は `sealib_name` / `sealib_o_name` / `sealib_id` 等の補完を行う**補助工程**であり、`ref_id` / `ref_name` の最終的な参照整合性保証は `enrich-db` ではなく SEALIB 側 Program2（§8.1、`docs/program2-resolution-strategy.md`）が投入時点に担う。
- **検証**: 一部列が空の main に対し、SEALIB DB から `name`/`o_name`/`issn` が補完されること。DB が無くても他コマンドが動くこと。

## 7. アダプタ contract（fetch-journal / enrich-db 共通の考え方）

- **fetch adapter（外部 CLI）**: 入力＝検索キー（`main.journal_name` 等）→ 出力＝候補配列（JSON）。各候補を journal 行へ写像。`journal_type` は呼び出し側が付与し、`grade` 正規化と `raw_json` 保存はツール側で行う。SINTA / Thai Tier はアダプタ差し替えで対応。
- **db adapter（補完）**: `lookup(key: id|name|o_name) -> record`。read-only。`SEALIBAdapter` は `header` テーブルを参照（旧 `read_sealib_rows` の方式）。将来は他図書館 DB 用アダプタを追加可能。

## 8. 破壊的変更・リスク

- **旧コマンド互換は提供しない**（破壊的）。旧 2 シート Excel の運用は退避した legacy ツールで継続。
- 旧 `export` の TSV 列（`metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note`、`EXPORT_HEADERS` `:61-70`）→ 新 `convert` の TSV 列は変わる。**SEALIB 取込側（`import-data-ext`）の整合確認が必要**。
- **convert → SEALIB `journal_metrics` マッピング**（`ref_id, ref_name, metric_source, metric_country, grade, url, note, imported_at`、`METRICS_MATCH_KEY` = `id` 既定）:
  | convert | journal_metrics |
  | --- | --- |
  | `id` | `ref_id` |
  | `journal_name` | `ref_name` |
  | `journal_type` | `metric_source` |
  | `grade` | `grade` |
  | `profile_url` | `url` |
  | `note` | `note` |
  - `external_journal_id` / `affiliation` は `journal_metrics` に列なし → **既定: `note` へ集約**（SEALIB 無改修）。代替: スキーマ拡張は別タスク。
  - **[Phase 3F]** 上記の `id`→`ref_id` / `journal_name`→`ref_name` 直結マッピングは (A) 直結方式の想定であり、**Phase 3F で不採用と決定**した。正式な投入方式は §8.1 を参照（`convert` は `ref_id`/`ref_name` を確定しない）。本表自体は Phase 4A で再設計する。
- `eissn` は SEALIB `header` に列が無く、ツール側保持のみ（DB へ同期しない）。
- 退避によりファイルパス/呼び出しが変わる（旧を直接叩く運用があれば周知）。

## 8.1. Program2投入方式の正式決定（Phase 3F）

Phase 3F（Phase 3E の SEALIB REST API v1 / OAI-PMH 2.0 整合性調査を踏襲）で、SEALIB側 Program2（`journal_metrics` 投入）の方式を **(B) 名前再解決方式** に正式決定した。詳細は `docs/program2-resolution-strategy.md` を参照。

- **採用方式: (B) 名前再解決方式**
  - `convert` は `ref_id` / `ref_name` を確定しない。
  - Program2 が投入時点の SEALIB DB で `header` を再解決する（`sealib_name` / `sealib_o_name` の完全一致検索、`sealib_id` は補助）。
  - `ref_id` = 解決後の `header.id`
  - `ref_name` = 解決後の `header.name`

- **(A) 直結方式（`convert.id`→`ref_id`、`convert.journal_name`→`ref_name`を無条件にそのまま投入する方式）は不採用**。`header.id` は SEALIB のフルビルドで変わりうるため、直結すると `ref_id` が既に存在しない ID を指して孤立するリスクがある。孤立した `ref_id` が残っていても REST API `?include=metrics` はエラーを返さず `metrics: []` を返すだけのため、指標がサイレントに表示されなくなる問題に運用上気づきにくい。これら2点が不採用の主な理由である。

- **enrich-db の位置付け**: `enrich-db`（§6 Phase 4）は `main` へ `sealib_name` / `sealib_o_name` / `sealib_id` 等を補完する**補助工程**であり、`ref_id` / `ref_name` の最終的な参照整合性保証は `enrich-db` ではなく **SEALIB 側 Program2 が投入時点に担う**。

§4 の `convert` 列構成（`id, journal_type, grade, external_journal_id, profile_url, journal_name, affiliation, note, convert_status`）は上記決定に基づき **Phase 4A** で再設計する。

## 9. 推奨方針

1. **Phase 1 から最小実装で着手**し、各 Phase 完了後にレビュー（Claude 観点整理 → Codex 実装 → 再レビュー）。
2. 旧 `metrics_excel.py` は legacy reference として扱い、拡張しない。移動・削除は別タスク化する。
3. **adapter contract（§7）を最初に固める**ことで SINTA / Thai Tier を差し替え可能にする。
4. `convert → DB` は SEALIB 既存 `journal_metrics` スキーマ維持（extra は `note` 集約）を既定とし、スキーマ拡張は別タスク候補。
5. 実装は Codex、Claude は設計・整理・レビュー・リリース判定を担当。

## 10. 関連ドキュメント

- `docs/adapter-contract.md` — fetch-journal / enrich-db アダプタ契約
- `docs/sealib-api-oai-compatibility-audit.md` — SEALIB REST API v1 / OAI-PMH 2.0 と journal_metrics 投入の整合性調査（Phase 3E）
- `docs/program2-resolution-strategy.md` — Program2投入方式の設計判断。(B) 名前再解決方式を正式採用（Phase 3F、§8.1）
