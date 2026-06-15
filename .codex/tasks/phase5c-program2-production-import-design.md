# Phase 5C: Program2 本番投入モード設計（記録）

## 目的

`seas-3.4.0` `admin/import-data-ext/03-2-import-metrics.php`（Phase 5Bで`--dry-run`のみ実装済み）の`--apply`（本番投入）モードを設計する。

## 対象

- `../../sealib/seas-3.4.0/admin/import-data-ext/03-2-import-metrics.php` の `--apply` モード（設計提案のみ・未実装）

## 制約

- 本フェーズはコード変更を行わない。
- DB書き込み実装は行わない。
- **`../../sealib/seas-3.3.1`（現行運用版）は対象外であり、絶対に変更しない。**
- REST API v1 / OAI-PMH 2.0 を変更しない。
- `header`テーブルの更新を行わない。
- journal-metrics-tools側（Excel/`journal_metrics.py`）を変更しない。
- 本番データの投入を行わない。

## 必ず読んだファイル

- `../../sealib/seas-3.4.0/admin/import-data-ext/03-2-import-metrics.php`（Phase 5B実装済み`--dry-run`。`resolve_row()`/`planned_insert_row()`/`write_report()`/起動時ガードL275-278）
- `../../sealib/seas-3.4.0/admin/import-data-ext/03-1-import-metrics-sinta.php`（トランザクション・INSERT・`imported_at`の参考実装）
- `../../sealib/seas-3.4.0/admin/import-data-ext/01-3-create-metrics-table.php`（`journal_metrics`スキーマ定義）
- `../../sealib/docs/journal-metrics-semi-auto-design.md`（§6 Program2設計原典、§9 ソース単位置換の方針）
- `docs/program2-dry-run-design.md`（Phase 5A）
- `docs/validation-layering.md`（Phase 5A-2）
- `docs/program2-resolution-strategy.md`（Phase 3F）

## 決定内容（要約）

- `--apply`は既存`--dry-run`のCLI（`--input`/`--db ext|core`/`--report`）を拡張し、`resolve_row()`/`planned_insert_row()`/5カテゴリ分類を共通利用する。新規ツールは作らない。
- CLI: `php 03-2-import-metrics.php --input <tsv> --db ext|core --apply [--backup] [--source <metric_source>]`
- 安全ガード: `--apply`必須。`resolve_row()`結果に`ambiguous`/`unmatched`/`invalid`が1件でもあれば中止（既存`--dry-run`の`exit(1)`条件と同一）。`warning`は投入可だがsummaryに明示。
- バックアップ: `--apply`時デフォルトで実施。命名規則`admin/archives/<DBファイル名>_<YYYYMMDD-HHMMSS>.bak`（`journal-metrics-semi-auto-design.md` §6.2-6.10 step2踏襲）。失敗時は投入中止。`--backup`は明示用の冗長フラグ。`--no-backup`はPhase 5D実装を任意（本番非推奨）。
- トランザクション: `--db`指定の1DBにつき1トランザクション。distinct `metric_source`（`--source`指定時はその1値）ごとにDELETE→INSERTをループし最後にCOMMIT。失敗時ROLLBACK。
- DELETE方針: `metric_source`単位のみ。`metric_country`は条件に含めない（`journal-metrics-semi-auto-design.md` §9踏襲、理由は本書§6に記載）。
- core/ext: 1コマンド=1DB。両DB投入は2回実行。`--db both`は本書スコープ外・別タスク。

詳細は`../../sealib/docs/program2-production-import-design.md`を参照。

## 検証項目

1. `../../sealib/docs/program2-production-import-design.md`が作成されていること。
2. `.codex/tasks/phase5c-program2-production-import-design.md`（本ファイル）が作成されていること。
3. `../../sealib/seas-3.3.1`に変更がないこと。
4. コード変更がないこと（`03-2-import-metrics.php`含む）。
5. `--apply`/バックアップ/トランザクション/DELETE/INSERT方針が明記されていること。

## Phase 5Dへの引き継ぎ

Phase 5Dで実施すべき最小作業（実装はまだ依頼しない。開始時に個別の`.codex/tasks/phase5d-*.md`を作成する）:

1. **起動時ガードの拡張**: `--dry-run`/`--apply`いずれも無い・両方ある場合はエラー。
2. **`--apply`実装**: `resolve_row()`を再利用し、安全ガード（`ambiguous`/`unmatched`/`invalid` > 0 で中止）を実装。
3. **バックアップ実装**: 命名規則に従いDBファイルをコピー。失敗時は中止。
4. **トランザクション実装**: `beginTransaction`/`commit`/`rollback`（書き込み可能PDO接続への切替）。
5. **`metric_source`単位DELETE実装**: `--source`オプションによる絞り込みを含む。
6. **INSERT実装**: `imported_at`付与を含む。
7. **投入後検証実装**: `GROUP BY metric_source`集計、dry-run結果との件数一致確認。

## Suggested Commit Message

```text
docs: design Program2 production import (--apply) mode for seas-3.4.0 (Phase 5C)
```
