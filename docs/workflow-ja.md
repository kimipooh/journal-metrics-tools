# 運用手順書

本書は Journal Metrics Tools を使用して学術誌の書誌情報および評価情報を収集・照合し、検証済み TSV ファイルを出力するための詳細手順を説明します。

---

## ワークフロー概要

```
template
  └─ ワークブックを新規作成
        ↓
  main シートに雑誌情報を入力（手動）
        ↓
  fetch-journal --adapter sealib   （任意: main.id / main.issn の補完）
        ↓
  fetch-journal --adapter sinta    （SINTA 評価情報の取得）
        ↓
  journal シートのレビュー         （手動: 候補の確認・除外設定）
        ↓
  convert                          （変換行の生成）
        ↓
  export-tsv                       （TSV ファイルの出力）
        ↓
  validate-tsv                     （DB 投入前の構造検証）
        ↓
  [後段 import ツール]              （本ツールのスコープ外）
```

---

## Step 1 — ワークブックの新規作成

```bash
python journal_metrics.py template --output my_journals.xlsx
```

以下の 4 シートを持つ Excel ワークブックを作成します。

| シート | 用途 |
|---|---|
| `README` | 列の説明（自動生成） |
| `main` | 雑誌リスト（人が編集する入力シート） |
| `journal` | 取得候補（`fetch-journal` が書き込む） |
| `convert` | TSV 出力用変換行（`convert` が書き込む） |

---

## Step 2 — main シートへの入力

`my_journals.xlsx` を Excel で開き、`main` シートを編集します。

### 列の説明

| 列名 | 必須/任意 | 説明 |
|---|---|---|
| `name` | **必須** | 雑誌名。SEALIB adapter を使う場合は DB の `header.name` と完全一致させてください。 |
| `status` | **必須** | 新規行は空欄または `pending` に設定。 |
| `o_name` | 任意 | 原語名（例: インドネシア語タイトル）。SEALIB 検索の補助キーとしても使用。 |
| `id` | 任意 | SEALIB `header.id`。空欄でも可（SEALIB adapter が補完）。 |
| `issn` | 任意 | Print ISSN。SINTA で同名候補が複数ある場合の ISSN 照合に使用。 |
| `eissn` | 任意 | Electronic ISSN。ISSN 照合に使用。 |
| `journal_name` | 任意 | 外部ソース上の候補名・確認対象名。`search_query` が空の場合のフォールバック検索キー。 |
| `search_query` | 任意 | SINTA 等の外部 adapter に渡す検索語。`journal_name` より優先。SEALIB adapter は使用しない。 |
| `note` | 任意 | 備考（自由記述）。 |

### 入力の注意点

- `name` は SEALIB adapter が `header.name` との名前照合に使用するキーです。SEALIB adapter を使う場合は DB 登録名と完全一致させてください。
- `search_query` は SINTA 検索用の検索語です。`name` と異なってよい（例: 出版社名を除いた短縮形）。
- `status = skip` に設定した行は全 fetch 操作の対象外になります。
- `status = done` に設定した行も同様に skip されます。
- `main.name` は adapter によって上書きされることはありません。

---

## Step 3 — SEALIB による識別子の補完（任意）

SEALIB（東南アジア逐次刊行物総合目録データベース: https://sealib.cseas.kyoto-u.ac.jp/）の SQLite DB を read-only 参照し、空欄の `main.id` / `main.issn` / `main.o_name` を補完します。SEALIB DB が利用できない場合や識別子が事前入力済みの場合はこのステップを省略できます。

```bash
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sealib \
    --db-path /path/to/sealib.sqlite \
    --country Indonesia        # 任意: 国フィルタ
```

**動作の詳細:**

- `main.name`（空なら `main.o_name`）で SEALIB `header` テーブルを検索
- 1 件だけ一致した場合のみ、空欄の `main.id` / `main.issn` / `main.o_name` を補完
- **`main.status` は変更しない**（`pending` のまま、後続の SINTA fetch が処理できる）
- 既存値と `main.name` は上書きしない
- `journal` シートには `journal_type = SEALIB` の行が記録される。この行は `convert` で `skipped` となり TSV には出力されない

**このステップを使う場面:**

- `main.id` や `main.issn` が未設定で SEALIB DB にアクセスできる場合
- 補完された ISSN は SINTA 取得時の ISSN 照合に使われ、候補の絞り込み精度が上がる

---

## Step 4 — SINTA からの評価情報取得

外部 CLI（`sinta-full-cli-v3`）を subprocess として呼び出し、SINTA から評価情報の候補を取得します。

```bash
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sinta \
    --sinta-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
    --sinta-python  ../sinta-full-cli-v3/.venv/bin/python
```

**動作の詳細:**

- `main.status` が 空欄 / `pending` / `adapter_error` の行を処理対象とする
- `main.search_query`（空なら `main.journal_name`）を検索キーとして使用
- 結果は `journal` シートに `journal_type = SINTA` の行として追記される
- `main.status` が更新される:

| 取得結果 | `main.status` |
|---|---|
| 1 件確定 | `fetched` |
| 複数候補、title 照合で 1 件に絞り込み | `fetched` |
| 複数候補、ISSN 照合で 1 件に絞り込み | `fetched` |
| 複数候補、絞り込み不可 | `multiple_candidates` |
| 0 件 | `not_found` |
| CLI エラー / タイムアウト | `adapter_error` |

**ISSN 補助照合の仕組み:**

SINTA が同名の候補を複数返した場合、`main.issn` / `main.eissn` と候補の ISSN を照合して自動的に 1 件に絞り込みます。basic 検索で ISSN が得られなかった場合は detail mode を追加実行して ISSN を取得します。それでも絞り込めない場合は `multiple_candidates` のまま残します。

**処理速度について:**

1 件あたり 30〜60 秒かかる場合があります。22 件であれば 11〜22 分程度を見込んでください。途中で中断しても、`fetched` / `not_found` 済みの行は次回実行時にスキップされます（`--update` を使わない限り）。

---

## Step 5 — journal シートのレビュー

Excel でワークブックを開き、`journal` シートを確認します。

| `fetch_status` | 意味 |
|---|---|
| `ok` | 候補確定。`convert` で変換行が生成される |
| `multiple` | 複数候補が残存。手動対応が必要な場合がある |
| `none` | 候補なし |
| `error` | adapter エラー。`fetch-journal` で再試行可能 |

手動除外が必要な行は `main.status = skip` に設定します。
処理完了とみなす行は `main.status = done` に設定します。
`skip` / `done` 以外の行は `--update` で再取得対象になります。

---

## Step 6 — convert シートへの変換

```bash
python journal_metrics.py convert --input my_journals.xlsx
```

`fetch_status = ok` の `journal` 行を読み込み、`convert` シートに行を生成します。

| `journal_type` | grade | `convert_status` | TSV 出力 |
|---|---|---|---|
| `SINTA`, `THAI_TIER` | あり | `ready` | される |
| `SINTA`, `THAI_TIER` | なし | `hold` | されない（grade 欠損を確認） |
| `SEALIB`, `MOCK` | — | `skipped` | されない（参照・テスト用） |

`convert` は毎回全行を削除してから再生成します。再実行しても古い行が残って二重化しません。

---

## Step 7 — TSV への出力

```bash
python journal_metrics.py export-tsv --input my_journals.xlsx --output output.tsv
```

`convert_status = ready` の行のみをタブ区切り TSV ファイルとして出力します。
既存ファイルは上書きされます。

---

## Step 8 — TSV の構造検証

```bash
python journal_metrics.py validate-tsv --input output.tsv
```

DB 接続不要で TSV の構造・形式を検証します。

- 列数・ヘッダ名の確認
- 各行の `sealib_name` / `sealib_o_name` / `sealib_id` のいずれかが必須
- `errors`（ブロッキング）と `warnings`（確認推奨）を報告

**DB 投入前の必須条件:**

```
errors = 0
```

`warnings > 0` の場合は各 warning を確認し、問題がないと判断できれば次に進んでください。

---

## Step 9 — 後段 import ツールへの引き渡し

`validate-tsv` で `errors = 0` が確認できれば、TSV ファイルは import 可能な状態です。

後段データベースへの投入は **Journal Metrics Tools のスコープ外** です。
ご利用の import ツールのドキュメントに従って次のステップを実施してください。

---

## 更新ワークフロー（`--update`）

取得済み評価情報を再取得する必要がある場合は、`--update` を使用します。

```bash
# SINTA 評価情報を再取得（status=skip/done 以外の全行）
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sinta \
    --update \
    --sinta-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
    --sinta-python  ../sinta-full-cli-v3/.venv/bin/python

# 変換行を再生成し、TSV を再出力・再検証
python journal_metrics.py convert   --input my_journals.xlsx
python journal_metrics.py export-tsv --input my_journals.xlsx --output output.tsv
python journal_metrics.py validate-tsv --input output.tsv
```

**`--update` の動作:**

- 処理対象: `status` が 空欄 / `pending` / `adapter_error` / `fetched` / `not_found` / `multiple_candidates` の行
- 処理対象外: `status = skip` / `done` の行
- 同じ `main` 行の既存 SINTA `journal` 行を削除してから新結果を書き込む（古い評価情報と新しい評価情報が混在しない）
- SEALIB / MOCK など他 adapter の `journal` 行は削除しない

`--update` は `fetch-journal` の再取得のみを行います。TSV へ反映するには `convert` → `export-tsv` → `validate-tsv` を明示的に再実行してください。

---

## トラブルシューティング

### SINTA CLI が見つからない

```
ERROR: --sinta-command is required when --adapter sinta
```

`--sinta-command` に `sinta-full-cli-v3.py` の正しいパスを指定しているか確認してください。

### `adapter_error` 行が残る

SINTA CLI がタイムアウト・ネットワークエラー・パス誤りで失敗しています。
`fetch-journal --adapter sinta`（`--update` なし）を再実行すると、
`main.status = adapter_error` の行が自動的に再試行されます。

### `multiple_candidates` 行が残る

SINTA が複数候補を返し、ISSN 照合でも絞り込めなかった行です。以下を試してください:

1. `main.issn` / `main.eissn` を記入または修正して `fetch-journal` を再実行
2. `main.search_query` をより具体的な検索語に変更して再実行
3. 恒久的に除外する場合は `main.status = skip` に設定

### `validate-tsv` でエラーが出る

よくある原因:

- `sealib_name`（= `main.name`）が空: `main` シートの `name` 列を入力してください
- 列数の不一致: `export-tsv` を再実行して TSV を再生成してください

### SEALIB adapter で `not_found` になる

`main.name` が SEALIB DB の `header.name` と一致していません。以下を確認してください:

- 表記ゆれ・末尾の句読点の有無
- `main.name` を DB 登録名と完全一致させる
- `main.o_name` に別名を設定して SEALIB 検索の補助キーとする

### `validate-tsv` 後の後段 import でマッチしない行が出る

`main.name`（= TSV の `sealib_name`）が SEALIB DB の `header.name` と一致していない可能性があります。
DB の正式登録名を確認し、`main.name` を修正してから `convert` → `export-tsv` → `validate-tsv` を再実行してください。
