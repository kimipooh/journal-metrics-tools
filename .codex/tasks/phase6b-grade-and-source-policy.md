# Phase 6B: grade と metric_source の投入ポリシー整理（記録）

## 目的

Phase 6A の実データ検証で、SEALIB adapter由来のconvert行は `sealib_name`/`sealib_id` は埋まるが `grade` が空になり、`validate-tsv` がERRORになることが分かった。この結果を受けて、`metric_source` の役割分類・`grade` の必須方針・SEALIB adapterの位置付け・`convert_status` 決定ロジックの改修方針を整理する。

## 対象

- `journal_metrics.py` の `generate_convert_rows`（`convert_status` 決定ロジック、現状は `fetch_status=="ok"` のみで `"ready"` 固定）
- `metric_source`（= `journal_type` / `candidate.source`）の役割分類
- `adapters/sealib.py` のadapterとしての位置付け

## 制約

- 本フェーズはコード変更を行わない。
- SINTA adapter / Thai Tier adapter を実装しない。
- grade正規化を行わない。
- Program2（`03-2-import-metrics.php`）を変更しない。
- SEALIB DBへの書き込みを行わない。
- 本番データの投入を行わない。
- 既存ファイル（`journal_metrics.py`, `adapters/sealib.py`, `docs/convert-sheet-redesign.md`, `docs/program2-resolution-strategy.md`, `docs/validation-layering.md`, `docs/program2-dry-run-design.md`, `README.md`）は変更しない。

## 必ず読んだファイル

- `docs/convert-sheet-redesign.md`（`CONVERT_HEADERS`、convert生成ルール §7、`convert_status` 語彙）
- `docs/program2-resolution-strategy.md`（(B) 名前再解決方式）
- `docs/validation-layering.md`（`validate-tsv` 責務、`PROGRAM2_TSV_HEADERS`必須項目）
- `docs/program2-dry-run-design.md`（Program2 `--dry-run` 設計）
- `README.md`
- `journal_metrics.py`（`CONVERT_HEADERS`, `PROGRAM2_TSV_HEADERS`, `generate_convert_rows`, `export_tsv_command`, `validate_tsv_command`）
- `adapters/sealib.py`（`_candidate()` の `grade: None` 固定）
- `journal_mapper.py` / `adapters/mock.py`（`journal_type`/`grade` の伝播経路の確認）

## 決定内容（要約）

1. **grade**: Program2 TSVで必須のまま。`validate-tsv` の grade空=ERROR方針は維持する（journal_metrics.grade はREST APIで公開される主要フィールドのため）。
2. **metric_source の分類**:
   - metrics source（`SINTA`/`THAI_TIER`、未実装）: grade必須・Program2投入対象
   - reference source（`SEALIB`）: grade常に空・header照合/E2Eテスト用・投入対象外
   - test source（`MOCK`）: テスト専用・投入対象外
3. **SEALIB adapterの位置付け**: SEALIB DB上のjournal検索・照合・E2Eテスト用のreference adapter。`journal_metrics`への投入価値を持つ指標データ（grade/url/note）を提供しないため、metrics sourceではない。
4. **convert_status決定ロジック（Phase 6C案）**: `fetch_status=="ok"` の行について、
   - `metric_source` がreference/test source → `skipped`
   - `metric_source` がmetrics sourceかつ `grade` 空 → `hold`
   - `metric_source` がmetrics sourceかつ `grade` 非空 → `ready`
   - 未知の `metric_source` → `skipped`（安全側デフォルト）
5. **validate-tsv/export-tsvとの関係**: いずれも変更不要。`export-tsv` が `convert_status=="ready"` のみを出力する既存挙動により、grade空行・SEALIB/MOCK行は自然にTSVから除外され、`validate-tsv` のERROR条件に該当しなくなる。

詳細は `docs/grade-and-source-policy.md` を参照。

## 検証項目

1. `docs/grade-and-source-policy.md` が作成されていること。
2. `.codex/tasks/phase6b-grade-and-source-policy.md`（本ファイル）が作成されていること。
3. grade必須方針（validate-tsv維持）が明記されていること。
4. `metric_source` の3分類（metrics source / reference source / test source）が明記されていること。
5. SEALIB adapterの位置付け（reference adapter、metrics sourceではない、convert_statusをreadyにしない）が明記されていること。
6. `convert_status` 決定ロジック案（`ready`/`hold`/`skipped`の3値）が明記されていること。
7. Phase 6Cの最小実装候補が列挙されていること。
8. 既存ファイル（`journal_metrics.py`等）が変更されていないこと（コード変更なし）。

## Phase 6Cへの影響

- `journal_metrics.py` に `metric_source` 役割定義（whitelist/role mapping）を追加する。
- `generate_convert_rows` の `convert_status` 決定ロジックを `docs/grade-and-source-policy.md` §4.3 のルールに置き換える。
- `export-tsv`/`validate-tsv`/`CONVERT_HEADERS`/`PROGRAM2_TSV_HEADERS` はロジック変更不要。
- 単体テスト追加（SEALIB行→`skipped`、MOCK行→`skipped`、grade欠落のmetrics source行→`hold`、grade付きmetrics source行→`ready`）。
- `docs/convert-sheet-redesign.md` §7・`convert_status` 語彙への `hold` 追加の反映（ドキュメント整合性）。

## Suggested Commit Message

```text
docs: define grade/metric_source policy for convert_status (Phase 6B)
```
