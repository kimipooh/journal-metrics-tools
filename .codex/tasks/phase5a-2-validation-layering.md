# Phase 5A-2: validate-tsv / Program2 --dry-run 責務分担整理（記録）

## 目的

Phase 4D で実装済みの `validate-tsv` と、Phase 5A で設計したSEALIB Program2 `--dry-run` が重複・競合しないよう、Program2向けTSVの二段階検証として責務を明確化する。

## 対象

- journal-metrics-tools: `journal_metrics.py` の `validate_tsv_command`（実装済み・本フェーズでは変更しない）
- SEALIB側 Program2: `03-2-import-metrics.php --dry-run`（Phase 5A設計、未実装）

## 制約

- 本フェーズはコード変更を行わない。
- SEALIB DBへの書き込みを行わない。
- Program2を実装しない。
- `validate-tsv`を変更しない。
- 既存ファイル（`docs/program2-dry-run-design.md`, `docs/convert-sheet-redesign.md`, `docs/program2-resolution-strategy.md`, `docs/sealib-api-oai-compatibility-audit.md`, `README.md`, `journal_metrics.py`）は変更しない。

## 必ず読んだファイル

- `journal_metrics.py`（`PROGRAM2_TSV_HEADERS` L66-75, `validate_tsv_command` L474-537, `note_looks_like_json`/`note_has_key_value_format` L187-208）
- `docs/program2-dry-run-design.md`
- `docs/convert-sheet-redesign.md`
- `docs/program2-resolution-strategy.md`
- `docs/sealib-api-oai-compatibility-audit.md`
- `README.md`

## 決定内容（要約）

- `validate-tsv` ＝ 第1段階（TSV構造・書式検証、SEALIB DBを見ない）。Program2 `--dry-run` ＝ 第2段階（SEALIB DBに対するheader解決・整合性検証、read-only）。
- 両者の検証範囲は現状重複していない。`validate-tsv`は非空・列構成・`note`書式チェックのみ、`metric_source`ホワイトリスト判定とheader解決はProgram2 `--dry-run`側。
- 実行順序: `export-tsv` → `validate-tsv` → Program2 `--dry-run` → Program2本番投入。
- Phase 5Bでは、Program2側に`validate-tsv`の構造チェックを再実装せず、列存在確認（列順不問、`03-1`の`array_flip`方式）のみを最低限の防御として追加する。

詳細は `docs/validation-layering.md` を参照。

## 検証項目

1. `docs/validation-layering.md` が作成されていること。
2. `.codex/tasks/phase5a-2-validation-layering.md`（本ファイル）が作成されていること。
3. `validate-tsv`の責務（実装済みコードに基づく）が明記されていること。
4. Program2 `--dry-run`の責務が明記されていること。
5. 実行順序（export-tsv→validate-tsv→dry-run→本番投入）が明記されていること。
6. 検出する問題の対応表があること。
7. 既存ファイルが変更されていないこと（コード変更なし）。

## Phase 5Bへの影響

- Program2 `--dry-run`実装時、`validate-tsv`がカバーする構造チェック（ヘッダ完全一致・列数・必須項目空・`note`書式）を再実装しない。
- Program2は安全のため、TSVヘッダから`PROGRAM2_TSV_HEADERS`8列が列順不問で存在するかのみ確認する最低限のチェックを行う。
- `metric_source`ホワイトリスト検証はProgram2側（dry-run含む）の専管とする。
- 本書の決定は`docs/program2-dry-run-design.md`の既存内容と矛盾しないため、同文書の修正は不要（本書からの参照のみ追加）。

## Suggested Commit Message

```text
docs: clarify validate-tsv vs Program2 dry-run responsibilities (Phase 5A-2)
```
