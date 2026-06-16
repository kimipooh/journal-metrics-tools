# Journal Metrics Tools

複数の情報源から学術誌に関する情報を収集・確認・照合・変換するための
Excel ワークブックベースの CLI ツールです。

> **English version**: [README.md](README.md)

---

## 概要

**Journal Metrics Tools** は、複数の情報源から学術誌に関する情報を収集・確認・照合・変換するための
Excel ワークブックベースの CLI ツールです。

本ツールは adapter 方式を採用しており、書誌情報補完や外部評価情報など、異なる種類の情報源を
組み合わせて利用できます。現在は SEALIB と SINTA の adapter を実装していますが、特定のサービスに
依存しない拡張可能な構造を採用しています。

代表的なワークフロー:

1. 学術誌リストを Excel ワークブック（`main` シート）で管理する
2. adapter 経由で書誌情報・評価情報を収集する（例: SEALIB で識別子補完、SINTA で認定ランキング取得）
3. `journal` シートで候補を確認・確定する
4. 検証済み TSV ファイルを生成する

現在の実運用では SEALIB（東南アジア逐次刊行物総合目録データベース、https://sealib.cseas.kyoto-u.ac.jp/）のデータ構造を基盤としており、TSV 出力の列名（`sealib_name`、`sealib_id` 等）はこれを反映しています。SEALIB adapter は任意機能です。`main.id` / `main.issn` が事前に入力されていれば、SEALIB DB がなくても SINTA 取得・変換・出力を実行できます。

### 用語説明

| 用語 | 説明 |
|---|---|
| **SINTA** | インドネシア教育文化省が運営する学術誌評価インデックス（Sinta Kemdikbud）。グレード S1〜S6 で分類。 |
| **SEALIB** | 東南アジアの逐次刊行物の書誌情報・所蔵情報を提供するデータベース（[東南アジア逐次刊行物総合目録データベース](https://sealib.cseas.kyoto-u.ac.jp/)）。本ツールは SEALIB SQLite DB を read-only で参照し、雑誌名・ISSN 等を補完する（任意）。 |

---

## 機能

| コマンド | 説明 |
|---|---|
| `template` | 管理用 Excel ワークブックを新規作成 |
| `fetch-journal` | adapter を通じて書誌情報または評価情報を収集（SEALIB / SINTA / mock） |
| `convert` | 確定候補を TSV 投入用の変換行に変換 |
| `export-tsv` | `ready` 行を TSV ファイルとして出力 |
| `validate-tsv` | TSV の構造・形式を検証（DB 接続不要） |

**adapter の役割:**

| adapter | 役割 | 提供する情報 |
|---|---|---|
| `sealib` | 書誌情報補完 | SEALIB SQLite DB から `main.id` / `main.issn` / `main.o_name` を補完（任意） |
| `sinta` | 評価情報取得 | [`sinta-full-cli-v3`](https://github.com/kimipooh/sinta-full-cli-v3)（外部 CLI）経由で SINTA 認定ランキングを取得 |
| `mock` | テスト・検証 | 固定レスポンスを返す内蔵 adapter。外部ツール不要。 |

- `--update` フラグ: 取得済みレコードを再取得する。

adapter 方式を採用しているため、追加の書誌情報ソースや評価情報ソースを統合できる構造になっています。

---

## アーキテクチャ

```
ワークブック（main シート）
  ↓
Adapter
  ├─ SEALIB（書誌情報補完）
  ├─ SINTA（評価情報取得）
  └─ mock（テスト・検証）
  ↓
確認（journal シート — 候補の確定）
  ↓
変換（convert シート — 出力用行の生成）
  ↓
検証済み TSV
```

> データベースへの登録処理（SEALIB Program2 等）は本ツールのスコープ外です。

---

## 必要環境

- Python 3.11 以上
- `openpyxl >= 3.1, < 4`（`requirements.txt` でインストール）
- **SINTA 取得時のみ**: [`sinta-full-cli-v3`](https://github.com/kimipooh/sinta-full-cli-v3)（別リポジトリ）
- **SEALIB 識別子補完時のみ（任意）**: SEALIB SQLite データベースファイル（read-only 参照）

---

## インストール

```bash
git clone <このリポジトリの URL>
cd journal-metrics-tools

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

SINTA 取得を行う場合は、SINTA CLI ツールも併せてセットアップします。

```bash
cd ..
git clone https://github.com/kimipooh/sinta-full-cli-v3
cd sinta-full-cli-v3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

推奨ディレクトリ構成:

```
research-tools/
├── journal-metrics-tools/       # 本ツール
│   ├── journal_metrics.py
│   └── ...
└── sinta-full-cli-v3/           # SINTA CLI（SINTA 取得時のみ必要）
    └── sinta-full-cli-v3.py
```

---

## クイックスタート（mock adapter — 外部ツール不要）

```bash
# 1. ワークブックを作成
python journal_metrics.py template --output my_journals.xlsx

# 2. Excel で my_journals.xlsx の main シートを編集
#    必須列:
#      name         — 雑誌名（SEALIB adapter を使う場合は DB の正式登録名に合わせる）
#      status       — 空欄または "pending"
#    推奨列:
#      search_query — SINTA 等の外部 adapter に渡す検索語
#      o_name       — 原語名（任意）
#      issn         — Print ISSN（任意。SINTA 候補の ISSN 照合に使用）

# 3. mock adapter で動作確認
python journal_metrics.py fetch-journal --input my_journals.xlsx --adapter mock

# 4. convert シートに変換
python journal_metrics.py convert --input my_journals.xlsx

# 5. TSV 出力・検証
python journal_metrics.py export-tsv --input my_journals.xlsx --output output.tsv
python journal_metrics.py validate-tsv --input output.tsv
```

---

## SINTA 取得ワークフロー

詳細は [docs/workflow-ja.md](docs/workflow-ja.md) を参照してください。

```bash
# Step 1（任意）: SEALIB DB で main.id / main.issn を補完
#   - main.status は変更しない（pending のまま）
#   - SEALIB 行は convert で skipped になり TSV には出力されない
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sealib \
    --db-path /path/to/sealib.sqlite \
    --country Indonesia

# Step 2: SINTA から評価情報を取得
#   注意: 1 件あたり 30〜60 秒かかる場合があります
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sinta \
    --sinta-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
    --sinta-python  ../sinta-full-cli-v3/.venv/bin/python

# Step 3: 変換・出力・検証
python journal_metrics.py convert   --input my_journals.xlsx
python journal_metrics.py export-tsv --input my_journals.xlsx --output output.tsv
python journal_metrics.py validate-tsv --input output.tsv
```

---

## 更新ワークフロー

```bash
# SINTA 評価情報を再取得（status=skip/done 以外の全行を対象）
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sinta \
    --update \
    --sinta-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
    --sinta-python  ../sinta-full-cli-v3/.venv/bin/python

# 変換・再出力
python journal_metrics.py convert   --input my_journals.xlsx
python journal_metrics.py export-tsv --input my_journals.xlsx --output output.tsv
python journal_metrics.py validate-tsv --input output.tsv
```

`--update` では同じ adapter の既存 `journal` 行を削除してから新結果を書き込むため、
古い評価情報と新しい評価情報が混在しません。

---

## コマンド一覧

### `template`

```
python journal_metrics.py template --output OUTPUT
```

`README` / `main` / `journal` / `convert` の 4 シートを持つ Excel ワークブックを新規作成します。

---

### `fetch-journal`

```
python journal_metrics.py fetch-journal --input INPUT --adapter ADAPTER [options]
```

| オプション | 必須 | 説明 |
|---|---|---|
| `--input` | yes | `.xlsx` ファイルパス（上書き更新） |
| `--adapter` | yes | `mock` / `sealib` / `sinta` |
| `--update` | no | `fetched` / `not_found` / `multiple_candidates` の行を再取得。`skip` / `done` は除外 |
| `--db-path` | sealib 時 | SEALIB SQLite DB パス |
| `--country` | no | SEALIB 検索の国絞り込み（例: `Indonesia`） |
| `--sinta-command` | sinta 時 | `sinta-full-cli-v3.py` のパス |
| `--sinta-python` | no | SINTA CLI 用 Python インタープリタ（省略時は現在の Python） |
| `--sinta-timeout` | no | SINTA CLI のタイムアウト秒数 |

**`sealib` adapter の動作:**

- `main.name`（空なら `main.o_name`）で SEALIB `header` テーブルを検索
- 1 件確定した場合のみ、空欄の `main.id` / `main.issn` / `main.o_name` を補完
- `main.status` は変更しない（`pending` のまま維持）
- 既存値と `main.name` は上書きしない

**`sinta` adapter の動作:**

- `main.search_query`（空なら `main.journal_name`）で SINTA を検索
- 同名候補が複数ある場合は ISSN 照合で自動的に1件に絞り込む
- `main.status` が `pending` / 空欄 / `adapter_error` の行を処理対象とする

---

### `convert`

```
python journal_metrics.py convert --input INPUT
```

`fetch_status = ok` の `journal` 行から `convert` シート行を生成します。

| `journal_type` | grade | `convert_status` | TSV 出力 |
|---|---|---|---|
| `SINTA` | あり | `ready` | される |
| `SINTA` | なし | `hold` | されない |
| `SEALIB`, `MOCK` | — | `skipped` | されない |

`convert` は毎回全行を再生成するため、古い行が残って二重化しません。

---

### `export-tsv`

```
python journal_metrics.py export-tsv --input INPUT --output OUTPUT
```

`convert_status = ready` の行をタブ区切り TSV ファイルとして出力します。
既存ファイルは上書きされます。

---

### `validate-tsv`

```
python journal_metrics.py validate-tsv --input INPUT
```

TSV の構造・形式を検証します（DB 接続不要）。

- 列数・ヘッダ名を確認
- `sealib_name` / `sealib_o_name` / `sealib_id` のいずれかが必須
- `errors`（ブロッキング）と `warnings`（確認推奨）を報告
- DB 投入前に `errors = 0` であることを確認してください

---

## 制限事項

- **SINTA 取得速度**: 外部 CLI subprocess を呼び出すため、1 件あたり 30〜60 秒かかる場合があります。大量処理には時間の余裕をもってください。
- **TSV 出力形式**: 列名（`sealib_name`, `sealib_id` 等）は SEALIB フィールド命名規則に基づいています。TSV の後段ツールへの投入は本ツールのスコープ外です。
- **`enrich-db` コマンド**: 実装予定ですが現在は未実装です。
- **SEALIB adapter**: ローカルの SQLite ファイルを read-only 参照します。REST API やネットワークアクセスは行いません。
- **GUI なし**: コマンドライン専用です。Excel ワークブックはデータ管理ストアとして使用し、表示ツールとしての利用は想定していません。

---

## ドキュメント

| ドキュメント | 言語 | 内容 |
|---|---|---|
| [README.md](README.md) | 英語 | English README |
| [docs/workflow-ja.md](docs/workflow-ja.md) | 日本語 | 詳細な運用手順 |
| [docs/workflow.md](docs/workflow.md) | 英語 | Step-by-step workflow guide |
| [docs/adapter-contract.md](docs/adapter-contract.md) | 日本語 | Adapter contract 仕様（開発者向け） |

---

## 作者

木谷公哉（Kimiya Kitani）<br>
京都大学東南アジア地域研究研究所（Center for Southeast Asian Studies, Kyoto University）

---

## 引用

本ツールを研究に利用した場合は、以下の形式で引用してください。

```
Kitani, Kimiya. (2026). Journal Metrics Tools (Version 1.0.0).
Center for Southeast Asian Studies, Kyoto University.
https://github.com/kimipooh/journal-metrics-tools
```

DOI はアーカイブリリース後に追加予定です。

引用管理ソフトウェアで利用できる `CITATION.cff` ファイルをリポジトリに含めています。

---

## ライセンス

MIT License。Copyright (c) 2026 Kimiya Kitani。[LICENSE](LICENSE) を参照してください。
