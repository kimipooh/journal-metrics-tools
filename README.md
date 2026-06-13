# Journal Metrics Excel Tool

Journal Metrics Workflow は現在、旧 `metrics_excel.py` から切り離して再構築中です。新ワークフローのメイン CLI は `journal_metrics.py` です。

Phase 1 時点で利用可能な新 CLI コマンドは、空テンプレート Excel を生成する `template` のみです。`fetch-journal` / `convert` / `enrich-db` は Phase 2 以降で実装予定です。

旧 `metrics_excel.py` は legacy reference です。旧 SEALIB/SINTA 2 シート方式の参考・既存運用用として残しますが、新 Journal Metrics Workflow の本線ではありません。旧ファイルは移動・削除せず、直接拡張しない方針です。

旧 CLI は、SEALIB の対象誌を読み取り専用 SQLite SELECT で取得し、SINTA 候補をアダプタ（`sinta-full-cli-v3.py`）経由で Excel 対応表へ蓄積する外部 Python CLI でした。SEALIB DB への書込、`journal_metrics` への投入、`confirmed=1` の自動設定は行いません。

> **配置方針（research-tools 分離）**: 本ツールは取得ツール `sinta-full-cli-v3` とは**別リポジトリ**として `research-tools/` 配下に並列配置します。SINTA 取得ツールは**同梱しません**。設計の詳細は sealib リポジトリの `docs/sealib-journal-metrics-tools-design.md` を参照。

## Layout (research-tools)

```
research-tools/
├── sinta-full-cli-v3/                 # git clone（取得ツール・別リポジトリ）
│   └── sinta-full-cli-v3.py
└── sealib-journal-metrics-tools/      # 本ツール（独立リポジトリ）
    ├── journal_metrics.py             # 新 CLI（Phase 1: template のみ）
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

- 新 CLI `journal_metrics.py` が Phase 1 で必要とするのは `openpyxl` のみです。SINTA 側の依存は `sinta-full-cli-v3` 側で別途インストールします。

## Current command (Phase 1)

```bash
.venv/bin/python journal_metrics.py template --output journal_metrics.xlsx
```

このコマンドは `README` / `main` / `journal` / `convert` の 4 シートを持つ空テンプレート Excel を生成します。Phase 1 では外部 CLI、DB、adapter は呼びません。`status` 列は作成しますが、自動処理は行いません。

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
