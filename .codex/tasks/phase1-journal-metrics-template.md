# Phase 1: journal_metrics.py template command

## 目的

Journal Metrics Workflow の新実装を、旧 `metrics_excel.py` から切り離して開始する。Phase 1 では、新メイン CLI `journal_metrics.py` による空テンプレート Excel の生成だけを実装し、後続 Phase のための最小の足場を作る。

旧 `metrics_excel.py` は legacy reference として扱い、直接改造・移動・削除しない。必要に応じて Excel ヘルパ、ヘッダ名アクセス、status 駆動などの考え方だけを参照する。

## 対象ファイル

- `journal_metrics.py`（新規作成）
- `requirements.txt`（既存依存で不足がある場合のみ最小変更）
- `README.md` / `docs/`（Phase 1 実装後に必要な最小整合のみ。大規模な全文書き換えはしない）

## 実装範囲

- CLI エントリポイント `journal_metrics.py` を新規作成する。
- 次のコマンドを実装する。

```bash
python journal_metrics.py template --output journal_metrics.xlsx
```

- `--output` で指定した `.xlsx` を作成する。
- 生成シートは次の 4 つに固定する。
  - `main`
  - `journal`
  - `convert`
  - `README`
- まだ外部 CLI、DB、adapter は呼ばない。
- `status` 列は作るが、自動処理はしない。
- 依存は原則 `openpyxl` のみとする。

## 非対象

- `fetch-journal` は実装しない。
- `convert` は実装しない。
- `enrich-db` は実装しない。
- 旧 `metrics_excel.py` の移動・削除・直接改造はしない。
- 旧 `init` / `fetch` / `refresh` / `export` / `report` / `import-existing-master` との互換維持は行わない。
- SINTA / Thai Tier などの adapter contract 確定や外部 CLI 呼び出しは行わない。
- SEALIB DB への接続、読み込み、書き込みは行わない。

## 空テンプレート作成仕様

### `main` sheet

ヘッダ行のみ作成する。人が編集する入力フォームとして使う。

| 列 | 備考 |
| --- | --- |
| `id` | DB 側 ID。空可 |
| `name` | 名称 |
| `o_name` | 原語名 |
| `issn` | ISSN |
| `eissn` | eISSN。ツール側保持のみ |
| `journal_name` | 外部ツール検索キー |
| `note` | 備考 |
| `status` | `new` / `queued` / `fetched` / `reviewed` / `converted` / `hold` などを想定。Phase 1 では自動更新しない |

### `journal` sheet

ヘッダ行のみ作成する。Phase 2 以降で外部ツール取得結果を 1:N で追記するための受け皿。

| 列 | 備考 |
| --- | --- |
| `main_row_id` | `main` 行への参照 |
| `journal_type` | `SINTA` / `THAI_TIER` などを想定 |
| `external_journal_id` | 外部 ID |
| `journal_name` | 取得名称 |
| `affiliation` | 所属 |
| `grade` | 正規化グレード |
| `profile_url` | プロフィール URL |
| `fetch_status` | `ok` / `multiple` / `none` / `error` などを想定 |
| `fetched_at` | 取得時刻 |
| `raw_json` | アダプタ生出力 |

### `convert` sheet

ヘッダ行のみ作成する。Phase 3 以降で DB 投入用の確定行を生成するための受け皿。

| 列 | 備考 |
| --- | --- |
| `id` | DB 側 ID |
| `journal_type` | ソース種別 |
| `grade` | グレード |
| `external_journal_id` | 外部 ID |
| `profile_url` | URL |
| `journal_name` | 名称 |
| `affiliation` | 所属 |
| `note` | 備考 |
| `convert_status` | `ready` / `exported` / `imported` / `skipped` などを想定 |

## README sheet または説明行の扱い

- `README` sheet を作成し、この Excel が Journal Metrics Workflow 用テンプレートであることを短く記載する。
- `main` / `journal` / `convert` の各シートの役割を 1 行ずつ説明する。
- Phase 1 時点では外部 CLI、DB、adapter を呼ばないことを明記する。
- 説明はテンプレート利用者向けの最小限に留め、長い運用手順は書かない。

## journal_metrics.py の最小実装方針

- `argparse` で `template` サブコマンドを定義する。
- `template` は `--output` を必須引数にする。
- ワークブック作成、シート作成、ヘッダ設定を小さな関数に分ける。
- ヘッダは定数リストで管理し、セルアクセスは将来のヘッダ名ベース処理を想定しやすい形にする。
- 旧 `metrics_excel.py` からコードをそのままコピーせず、必要な考え方だけを反映する。
- 既存ファイルがある場合の上書き可否は Phase 1 実装時に明示する。迷う場合は安全側としてエラーにし、必要なら `--force` を別タスクで検討する。

## 検証コマンド

```bash
python journal_metrics.py template --output journal_metrics.xlsx
python -m py_compile journal_metrics.py
python - <<'PY'
from openpyxl import load_workbook
wb = load_workbook('journal_metrics.xlsx', read_only=True)
print(wb.sheetnames)
for name in ['main', 'journal', 'convert']:
    ws = wb[name]
    print(name, [cell.value for cell in ws[1]])
print('README rows', wb['README'].max_row)
PY
```

期待値:

- `['main', 'journal', 'convert', 'README']` が生成される。
- `main` / `journal` / `convert` のヘッダが rebuild plan と一致する。
- `README` sheet に最小説明が入っている。
- DB、adapter、外部 CLI なしで実行できる。

## 完了条件

- `journal_metrics.py template --output journal_metrics.xlsx` でテンプレート Excel が生成される。
- 生成シートが `main` / `journal` / `convert` / `README` の 4 つである。
- 各シートのヘッダが本タスク仕様と一致する。
- `status` / `fetch_status` / `convert_status` 列は存在するが、自動処理は行わない。
- `fetch-journal` / `convert` / `enrich-db` は未実装のままである。
- 旧 `metrics_excel.py` は変更されていない。
- 実装後の報告に、変更ファイル、変更理由、検証方法、残課題を含める。
