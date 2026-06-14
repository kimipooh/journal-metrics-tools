# Phase 2A: Adapter Contract 定義（完了サマリ／Phase 2B 引き継ぎ）

## Objective

`fetch-journal`（Phase 2）実装に先立ち、外部ソース（SINTA / Thai Tier / SEALIB / 将来ソース）から `journal` シートへ Journal Metrics 候補を渡すための共通 adapter contract を `docs/adapter-contract.md` として定義した。本タスクは **設計のみ**（コード変更なし）。

## Phase 2A 完了内容（要約）

- `docs/adapter-contract.md` を新規作成。
- レイヤー分離: adapter（外部ソース取得層）と fetch-journal（Excel 書き込み層）を分離。adapter は Excel I/O を行わない。
- 共通候補フィールド: `source` / `external_journal_id` / `title` / `issn` / `eissn` / `publisher` / `country` / `grade` / `url` / `note`（各フィールドの必須/任意・空値扱い・`journal` シート対応列を定義）。
  - `issn` / `eissn` / `country` / `note` は `journal` シートに直接対応列が無く、`raw_json` に保持。
  - `publisher` は既存列 `affiliation` を再利用（意味差は将来検討事項として明記）。
  - `grade` は adapter が raw 値を返し、正規化は fetch-journal 側で `journal_type` 別に実施。
- envelope: `{status, source, query, candidates[], error}`。
- 候補↔journal行の対応: 1 candidate = 1 journal 行（1 main 行に対し 1:N）。`main_row_id` は adapter の candidate（§4.1）に含めず、fetch-journal が付与する。複数候補の順序は、同一 `main_row_id` を持つ `journal` シート上の行順で保持する。`envelope.query` はトレーサビリティ用に保持。`candidate_rank` は現時点では採用せず、将来必要になった場合の拡張候補とする。
- status 語彙: `pending` / `fetched` / `not_found` / `multiple_candidates` / `adapter_error` / `confirmed` / `rejected`。
  - `envelope.status` ∈ {`fetched`, `not_found`, `multiple_candidates`, `adapter_error`} → `journal.fetch_status` ∈ {`ok`, `none`, `multiple`, `error`} に対応。
  - `pending` / `confirmed` / `rejected` は `main.status` 側の将来語彙（adapter 出力ではない）。
- 単一候補 / 複数候補 / not_found / adapter_error の JSON 入出力例を記載。
- 対応ソース方針: Phase 2B = mock adapter（外部接続なし）、Phase 2C 以降 = SEALIB adapter を含む実ソース adapter。

## Scope（Phase 2B — 次タスクの定義）

Phase 2B では、`docs/adapter-contract.md` に準拠する **mock adapter** を実装する。

- 外部 CLI・DB・ネットワーク接続は行わない。固定/サンプルの envelope（§5 の 4 パターン: fetched / multiple_candidates / not_found / adapter_error）を返せること。
- 実装方式（in-process 関数 / CLI 等）と `journal_metrics.py` への組み込み範囲は、Phase 2B タスク開始時に個別に定義する（本タスクでは確定しない）。
- Phase 2B 完了後、`fetch-journal` 本体（journal シートへの書き込み・`fetch_status` 決定・grade 正規化・`main_row_id` 付与）は Phase 2C 以降で扱う。複数候補の順序は `journal` シート上の行順で保持し、`candidate_rank` 列は追加しない（将来必要になった場合のみ別タスクで検討する）。

## Constraints

- 本タスク（Phase 2A）はコード変更を含まない。
- `journal_metrics.py` / `metrics_excel.py` は変更しない。
- `README.md` は本タスクでは変更しない（Phase 1 の記述で現状は十分であり、動作する CLI が無い段階で adapter contract を README に追記する実用的な内容が無いため）。
- 既存ファイルの大規模変更は行わない。

## Implementation Steps（本タスクで実施済み）

1. `docs/rebuild-plan.md` §7、`README.md`、`journal_metrics.py`、`.codex/tasks/phase1-journal-metrics-template.md` を確認。
2. `docs/adapter-contract.md` を新規作成（contract 定義）。
3. 本ファイル（`.codex/tasks/phase2a-adapter-contract.md`）を新規作成。

## Validation Steps

- `docs/adapter-contract.md` が存在し、`source` / `title` / `issn` / `eissn` / `grade` / `status` の説明を含む。
- `docs/adapter-contract.md` に `main_row_id` の責務分担（adapter は付与しない、fetch-journal が付与する）と、複数候補の順序を `journal` シート上の行順で保持する方針が明記されている。
- `.codex/tasks/phase2a-adapter-contract.md` が存在する。
- `journal_metrics.py` に差分がない。
- `metrics_excel.py` に差分がない。
- `README.md` に差分がない。

## Expected Deliverables

- `docs/adapter-contract.md`（新規）
- `.codex/tasks/phase2a-adapter-contract.md`（新規）

## Suggested Commit Message

```text
docs: define Phase 2A adapter contract for journal-metrics fetch
```
