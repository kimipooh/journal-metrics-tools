# Journal Metrics Excel Tool

Journal Metrics Workflow は現在、旧 `metrics_excel.py` から切り離して再構築中です。新ワークフローのメイン CLI は `journal_metrics.py` です。

Phase 7C 時点で利用可能な新 CLI コマンドは、空テンプレート Excel を生成する `template`、mock / SEALIB / SINTA adapter による `fetch-journal`、`convert`、`export-tsv`、`validate-tsv` です。`enrich-db` は後続 Phase で実装予定です。

旧 `metrics_excel.py` は legacy reference です。旧 SEALIB/SINTA 2 シート方式の参考・既存運用用として残しますが、新 Journal Metrics Workflow の本線ではありません。旧ファイルは移動・削除せず、直接拡張しない方針です。

旧 CLI は、SEALIB の対象誌を読み取り専用 SQLite SELECT で取得し、SINTA 候補をアダプタ（`sinta-full-cli-v3.py`）経由で Excel 対応表へ蓄積する外部 Python CLI でした。SEALIB DB への書込、`journal_metrics` への投入、`confirmed=1` の自動設定は行いません。

> **配置方針（research-tools 分離）**: 本ツールは取得ツール `sinta-full-cli-v3` とは**別リポジトリ**として `research-tools/` 配下に並列配置します。SINTA 取得ツールは**同梱しません**。設計の詳細は sealib リポジトリの `docs/sealib-journal-metrics-tools-design.md` を参照。

## Layout (research-tools)

```
research-tools/
├── sinta-full-cli-v3/                 # git clone（取得ツール・別リポジトリ）
│   └── sinta-full-cli-v3.py
└── sealib-journal-metrics-tools/      # 本ツール（独立リポジトリ）
    ├── journal_metrics.py             # 新 CLI（template / mock・SEALIB・SINTA fetch-journal）
    ├── metrics_excel.py
    ├── requirements.txt
    └── README.md
```

## Setup

```bash
mkdir -p research-tools && cd research-tools
git clone https://github.com/kimipooh/sinta-full-cli-v3
git clone <sealib-journal-metrics-tools の URL>

cd sealib-journal-metrics-tools
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt   # openpyxl
```

- 新 CLI `journal_metrics.py` が現時点で必要とするのは `openpyxl` のみです。SINTA 側の依存は `sinta-full-cli-v3` 側で別途インストールします。

## Current commands (Phase 7C)

```bash
.venv/bin/python journal_metrics.py template --output journal_metrics.xlsx
.venv/bin/python journal_metrics.py fetch-journal --input journal_metrics.xlsx --adapter mock
.venv/bin/python journal_metrics.py fetch-journal --input journal_metrics.xlsx --adapter sealib --db-path /path/to/sealib.sqlite
.venv/bin/python journal_metrics.py fetch-journal --input journal_metrics.xlsx --adapter sealib --db-path /path/to/sealib.sqlite --country Indonesia
.venv/bin/python journal_metrics.py fetch-journal --input journal_metrics.xlsx --adapter sinta --sinta-command ../sinta-full-cli-v3/sinta-full-cli-v3.py
.venv/bin/python journal_metrics.py fetch-journal --input journal_metrics.xlsx --adapter sinta --sinta-command ../sinta-full-cli-v3/sinta-full-cli-v3.py --sinta-python ../sinta-full-cli-v3/.venv/bin/python
```

`template` は `README` / `main` / `journal` / `convert` の 4 シートを持つ空テンプレート Excel を生成します。`fetch-journal --adapter mock` は mock adapter の固定レスポンスだけを使い、`main` シートの対象行から `journal` シートへ候補を書き込みます。

`main.journal_name` は外部ソース上の候補名・確認対象名として保持します。`main.search_query` は SINTA / Thai Tier / mock などの外部 adapter に渡す検索文字列です。外部 adapter は `search_query` を優先し、空の場合のみ移行補助として `journal_name` を使います。`name` には fallback しません。既存 workbook に `search_query` 列がない場合も、外部 adapter は `journal_name` があれば従来データを検索できます。

`fetch-journal --adapter sealib` は SEALIB SQLite DB を read-only 接続で参照し、DB照合用の `name`、空なら `o_name` を検索に使います。SEALIB adapter は `search_query` と `journal_name` を使いません。任意の `--country` を指定した場合は、SEALIB adapter 側で `header.country` を絞り込みます。SEALIB adapter は内部補完処理として扱い、`main.status` は変更しません（`pending` のまま後続の `--adapter sinta` が処理できます）。候補が1件だけ取得できた場合に限り、空欄の `main.id` / `main.issn` / `main.o_name` を SEALIB `header.id` / `header.issn` / `header.o_name` で補完します。既存値と `main.name` は上書きしません。`header.issn` / `header.o_name` が空の場合もエラーにはしません。

`fetch-journal --adapter sinta` は別リポジトリの `sinta-full-cli-v3.py` を subprocess で呼び出します。`--sinta-command` は必須で、SINTA CLI のスクリプトパスだけを指定します。SINTA CLI 用に別 venv を使う場合は `--sinta-python` を指定できます。検索キーは `main.search_query` を優先し、空の場合のみ移行補助として `main.journal_name` を使います。`main.name` には fallback しません。SINTA 検索で複数候補が返った場合でも、正規化後の候補 title が検索キーと完全一致するものが1件だけなら、その1件を `fetched` として自動確定します。title 完全一致候補が2件以上あり、`main.issn` / `main.eissn` のいずれかがある場合は、候補の `p_issn` / `e_issn` と照合し、一意に一致した場合だけ `fetched` とします。標準検索結果に ISSN が無い場合に限り、同条件下で `--fetch-mode detail` を追加実行して ISSN 補助照合を試みます。detail 取得失敗時は検索成功分を保持し、`adapter_error` にはせず `multiple_candidates` のままにします。

`fetch-journal --adapter sinta` は `main.status` が空欄 / `pending` / `adapter_error` の行を処理対象にします。`adapter_error` は SINTA CLI パス誤りや一時的な外部エラーからの再試行用 status です。adapter error が再発した場合は `main.status=adapter_error` を残し、`journal` シートには候補データ風の error 行を追加しません。再試行前に同じ `main` 行へ紐づく既存 `fetch_status=error` 行がある場合は削除し、正常候補行は削除しません。

`fetch-journal --update` は年次更新などで既存行を再取得するためのオプションです。完全空白行を除き、`main.status` が空欄 / `pending` / `adapter_error` / `fetched` / `not_found` / `multiple_candidates` の行を再処理します。`skip` / `done` は処理しません。`--adapter sinta --update` では、再取得前に同じ `main_row_id` かつ `journal_type=SINTA` の既存 `journal` 行を削除し、新しい結果だけを書き込みます。SEALIB 行や他 adapter 行は削除しません。`--adapter sealib --update` は空欄の `main.id` / `main.issn` / `main.o_name` だけを補完し、既存値と `main.status` は変更しません。

現時点の SEALIB adapter は `journal_metrics` テーブル参照、grade 取得、grade 正規化をまだ行いません。実 SEALIB DB での検証は DB パス確認後に行います。本番データ投入はまだ慎重に扱い、まずは少数のテスト行で `journal` シートへの追記結果と `main.status` 更新を確認してください。

`convert` は `journal.fetch_status == ok` の行から Program2 TSV 用の行を再生成します。Program2 の名前再解決に必要な `sealib_name` は `main.name`、`sealib_o_name` は `main.o_name` から設定します。`sealib_id` は SEALIB `header.id` 用の補助値です。`metric_source == SEALIB` の場合のみ `journal.external_journal_id`（SEALIB header.id）を使い、SINTA / MOCK / THAI_TIER など外部 source では `main.id` を使います。SINTA の `journal_id` は `sealib_id` には入れず、`note` の `external_id=...` として保持します。欠損値は空欄として扱い、`convert` ではエラーにしません。

`--update` は `fetch-journal` の再取得だけを行います。grade 変更などを Program2 TSV に反映するには、更新後に `convert`、`export-tsv`、`validate-tsv` を明示的に再実行してください。`convert` は実行時に既存 `convert` シートのデータ行を削除して再生成するため、古い convert 行は二重化しません。

`convert_status` は source role と grade の有無で決まります。`SINTA` / `THAI_TIER` は grade があれば `ready`、grade が空なら `hold` です。`SEALIB` / `MOCK` は参照・テスト用の source として `skipped` になり、`export-tsv` には出ません。`export-tsv` は `ready` 行だけを Program2 TSV に出力します。

SINTA から Program2 dry-run までの少数実データ検証では、`fetch-journal --adapter sinta` → `convert` → `export-tsv` → `validate-tsv` → `03-2-import-metrics.php --dry-run --db ext` が成立することを確認済みです。Program2 dry-run の name matching は `sealib_name`（= `main.name`）を SEALIB DB の `header.name` と照合するため、`main.name` は可能な限り SEALIB DB の正式名称に合わせてください。`search_query` は SINTA / Thai Tier 等の外部 adapter 用の検索語であり、Program2 再解決には使いません。

Program2 `--apply` 実行前の最終承認手順は、sealib リポジトリの `docs/program2-apply-runbook.md`（3.1〜3.3）に整理しています。必須条件は `validate-tsv` の `errors = 0`、dry-run成功、`ambiguous = 0` / `unmatched = 0` / `invalid = 0`、`planned_insert_rows` が想定件数と一致することで、推奨条件は `warning = 0` です。`warning > 0` の場合は report の `reason` と `main.name` / SEALIB DB `header.name` の一致を確認し、apply判定を **apply可** / **apply保留** / **workbook・mainシート修正後にdry-run再実行** の3区分で整理します。Phase 7J では同フローを SEALIB `header`（country=IO）15件で実行し、`fetched=4 / multiple_candidates=2 / not_found=9` のうち `ready` 4件で `ready_to_insert=4 / warning=0 / ambiguous=0 / unmatched=0 / invalid=0 / planned_insert_rows=4`（全件 `matched by name`）となることを確認しました。Phase 7K-1 では 22件（`phase7k-0-sinta-test.xlsx`）で同フローを実行し、title 完全一致複数候補を ISSN 補助照合で1件確定する処理も含め、22件すべてが `fetched=22`・`ready_to_insert=22`・`warning=0`・`ambiguous=0`・`unmatched=0`・`invalid=0`・`planned_insert_rows=22` となることを確認しました。Program2 `--apply` は未実行、DB 書き込みなし、本番 workbook 変更なしです。

## Legacy / Previous workflow

以下は旧 `metrics_excel.py` による legacy workflow の説明です。新 CLI `journal_metrics.py` の利用手順ではありません。

- SINTA 取得（`fetch` / `refresh`）では **`--adapter-command` でアダプタのスクリプトパスを明示**します。**既定値はありません**（未指定はエラー停止）。インタプリタは `--python`（既定: 実行中の Python）で指定し、`--adapter-command` には**スクリプトパスのみ**を渡します（`python3 ...` のようなインタプリタ込みコマンドは渡しません）。
- `--sinta-cli` は後方互換 alias です。`--adapter-command` と併用した場合は `--adapter-command` を優先し、警告を表示します。
- アダプタが別 venv を持つ場合は `--python ../sinta-full-cli-v3/.venv/bin/python` のように指定できます。

### Legacy commands

```bash
# 対応表の初期化（SEALIB DB は --db-path で明示・必須）
python metrics_excel.py init \
  --source SINTA --country ID --db ext \
  --xlsx master.xlsx \
  --db-path ./data/sqlite_library_seas_ext.db

# 既存の手動補完 Excel を取り込み
python metrics_excel.py import-existing-master \
  --in "書誌情報-…-SINTAツール分析-…-手動補完.xlsx" \
  --xlsx master.xlsx

# SINTA 取得（--adapter-command を明示）
python metrics_excel.py fetch \
  --xlsx master.xlsx \
  --adapter-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
  --fetch-mode basic \
  --resume

python metrics_excel.py fetch \
  --xlsx master.xlsx \
  --adapter-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
  --fetch-mode detail \
  --only needs_review \
  --resume

# 確定行の最新指標を再取得
python metrics_excel.py refresh \
  --xlsx master.xlsx \
  --adapter-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
  --resume

# DB import 用 TSV を出力（confirmed のみ）
python metrics_excel.py export \
  --xlsx master.xlsx \
  --out sinta-ID.tsv

python metrics_excel.py report \
  --xlsx master.xlsx
```

`fetch-mode` の既定は `basic` です。`detail` は明示指定時のみ使い、ISSN などの detail 列は生分析シートだけに保持します。ISSN は自動照合には使いません。`--fetch-mode` / `--mode` は **SINTA プロファイル固有**のフラグで、アダプタへ pass-through されます（汎用アダプタ共通契約ではありません）。

> パス例は `research-tools` 配下の**相対パス**を基本にしています。個人環境の絶対パスは運用メモ等の「ローカル例」として最小限にとどめてください。

## Legacy / Previous workflow Excel Sheets

- 生分析シート: `ID（SINTAツール分析）`
  - `query, journal_name, sinta_level, affiliation, journal_id, profile_url, fetched_at`
  - `detail` 実行時のみ `p_issn, e_issn, subject_area, website_url, editor_url, garuda_url, google_scholar_url` を追加
- 対応表シート: `ID (名前あり)`
  - `confirmed, status, metric_source, metric_country, sealib_id, sealib_name, sealib_o_name, issn, sinta_query_name, sinta_journal_name, sinta_journal_id, profile_url, sinta_level, garuda_name, fetched_at`

`affiliation` は生分析シートのみに保持し、対応表や export TSV には含めません。

## Legacy / Previous workflow Behavior

- `init`: `header` から `id, name, o_name, issn` を読み取り、対応表へ新規誌だけ追記します。既存行の司書補記欄は保持します。**`--db-path` は必須**です（SEALIB DB の SQLite ファイルを指定）。
- `import-existing-master`: 既存の手動補完 Excel から `インドネシア (名前あり)` と `インドネシア（SINTAツール分析）` を読み、Program 1 の正式2シートへ取り込みます。既定では `confirmed` を空欄にします。`--assume-confirmed` 指定時のみ、`sinta_query_name` と `profile_url` が揃う行を `confirmed=1` にします。シート名は `--src-sheet` / `--analysis-sheet` で変更できます。
- `fetch`: `sinta_query_name`、空なら `sealib_name` で検索します。候補1件のみ対応表へ自動転記し `status=auto_fetched`、0件/複数件は `status=needs_review` にします。アダプタ通信・HTTP・timeout 系の失敗は `status=fetch_error` にします。`confirmed` は変更しません。
- `refresh`: `confirmed=1` の行だけを対象に再検索し、保存済み `sinta_journal_id` と一致した候補の `sinta_level` と `fetched_at` だけを更新します。`--resume` は同日更新済み行をスキップします。
- `export`: `confirmed=1` の行だけを TSV 出力します。列は `metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note` です。

`needs_review` は SINTA 検索可能名が未確定の状態です。`fetch_error` は通信失敗などの再試行対象で、0件検索結果とは区別します。

## Legacy / Previous workflow Grade Normalization

export 時に次を正規化します。

- `S1 Accredited` から `S6 Accredited`: 正規形として保持
- `Sinta 1` / `SINTA 1` / `S1` から `S1 Accredited`
- `Sinta 2` / `SINTA 2` / `S2` から `S2 Accredited`
- 同様に S1 から S6 まで対応
- 空欄は空欄のまま
- 判定不能な値は raw 値を保持し、標準エラーに warning を出力

## Legacy / Previous workflow Country Code Note

`--country ID` は metrics の国コードとして Excel/TSV に保持します。SEALIB の `header.country` は LC コードのため、既定では `ID` を `IO` に変換して SELECT します。必要に応じて `init --sealib-country IO` のように明示指定できます。

## Legacy / Previous workflow Migration note（co-located → research-tools）

- 本ツールは旧 `sealib/tools/sinta-full-cli-v3/metrics_excel.py`（取得ツール同居）から `research-tools/sealib-journal-metrics-tools/`（独立リポジトリ）へ移設する方針です。
- アダプタ指定は `--sinta-cli`（同一ディレクトリ既定）から **`--adapter-command`（スクリプトパス・既定値なし・明示必須）** に変更しました。`--sinta-cli` は**後方互換 alias** として残ります。
- SEALIB DB の参照はリポジトリ相対の自動発見（旧 `parents[2]`）を廃止し、**`init --db-path` を必須化**しました。
- 旧 `sealib/tools/sinta-full-cli-v3/` のコピーは**この変更では削除しません**（撤去は別タスク）。独立 GitHub リポジトリ作成・`research-tools/` への物理移動も別手順です。
- `import-existing-master` / `fetch_error` は本移設で追加・変更していない**既存機能**です。
