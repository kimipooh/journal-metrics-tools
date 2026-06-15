# Phase 5A: Program2 dry-run 設計（記録）

## 目的

Program2（`03-2-import-metrics.php`）の本番投入（DELETE+INSERT）実装前に、入力TSVをSEALIB DBに対してread-onlyで検証し、投入予定行・`unmatched`・`ambiguous`・`warning`を確認できる`--dry-run`モードの仕様を設計する。

## 対象

- SEALIB側 Program2（`03-2-import-metrics.php --dry-run`、未実装。設計提案のみ）

## 制約

- 本フェーズはコード変更を行わない。
- SEALIB DBへの書き込み（DELETE/INSERT/バックアップ/トランザクション）を行わない。dry-run自体も含め実装しない。
- REST API v1 / OAI-PMH 2.0 を変更しない。
- journal-metrics-tools側のExcel（`main`/`journal`/`convert`）を変更しない。
- 本番データ投入を行わない。
- 既存ファイル（`docs/program2-resolution-strategy.md`, `docs/convert-sheet-redesign.md`, `docs/sealib-api-oai-compatibility-audit.md`, `docs/rebuild-plan.md`, `journal_metrics.py`, sealib側ドキュメント・PHPファイル一式）は変更しない。

## 必ず読むファイル

- `docs/program2-resolution-strategy.md`
- `docs/convert-sheet-redesign.md`
- `docs/sealib-api-oai-compatibility-audit.md`
- `docs/rebuild-plan.md`
- `journal_metrics.py`
- sealib `docs/journal-metrics-semi-auto-design.md`
- sealib `admin/import-data-ext/03-1-import-metrics-sinta.php`
- sealib `admin/import-data-ext/01-3-create-metrics-table.php`

## 決定内容（要約）

- dry-runは新規ツールではなく、`journal-metrics-semi-auto-design.md` §6が計画する `03-2-import-metrics.php` の `--dry-run` モードとして設計する。
- 入力TSVは8列固定: `metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note`（`docs/convert-sheet-redesign.md` §9と同一）。
- header解決は「名前優先・ID補助」アルゴリズム（§3）により5カテゴリへ分類する: `ready_to_insert` / `warning` / `ambiguous` / `unmatched` / `invalid`。
- `ready_to_insert`・`warning`はINSERT予定行（`ref_id`=解決後`header.id`、`ref_name`=解決後`header.name`、ほかTSV値そのまま、`imported_at`は未設定）を生成する。`ambiguous`/`unmatched`/`invalid`はスキップ・ログのみ。
- レポートは標準出力サマリ（カテゴリ別件数、core/extそれぞれ）+ 任意のTSVレポート（行ごとの解決結果）。JSONレポートは本フェーズでは不要。
- dry-runはcore/ext DBそれぞれに対して独立実行する。core/ext間の解決結果差分検出はPhase 5B以降の検討対象として明記。

詳細は`docs/program2-dry-run-design.md`を参照。

## 検証項目

1. `docs/program2-dry-run-design.md`が作成されていること。
2. `.codex/tasks/phase5a-program2-dry-run-design.md`（本ファイル）が作成されていること。
3. DB書き込み（DELETE/INSERT/バックアップ）がスコープ外と明記されていること。
4. header解決ルール（名前優先・ID補助、5カテゴリ分類アルゴリズム）が明記されていること。
5. `ready_to_insert`/`unmatched`/`ambiguous`/`warning`/`invalid`の分類が定義されていること。
6. Phase 5Bの実装範囲が明記されていること。
7. 既存ファイルが変更されていないこと（コード変更なし）。

## Phase 5Bへの引き継ぎ

Phase 5Bで実施すべき最小作業（実装はまだ依頼しない。開始時に個別の`.codex/tasks/phase5b-*.md`を作成する）:

1. **dry-run CLI実装**: `03-2-import-metrics.php --dry-run`として、TSV読み込み→header解決→レポート出力→終了（バックアップ/トランザクション/DELETE/INSERTの手前で停止）を実装する。
2. **read-only SQLite接続**: `mode=ro`のPDO/SQLite接続（`03-1-import-metrics-sinta.php`の接続方式をread-only化）。
3. **TSV parse**: `docs/program2-dry-run-design.md` §2の8列をヘッダ名ベースで判定（`03-1`の`array_flip`方式を流用、列順は任意）。
4. **header解決ロジック**: `docs/program2-dry-run-design.md` §3のアルゴリズム（candidates取得・件数分岐・5カテゴリ判定）を実装する。
5. **レポート出力**: §6の標準出力サマリ（必須、core/ext別）+ TSVレポート（任意）を実装する。
6. **metric_sourceホワイトリスト**: `journal-metrics-semi-auto-design.md` §6.3の設定値をdry-runにも適用する。
7. **(将来検討)** core/ext間の解決結果差分検出は、§7で方向性のみ示した設計提案であり、Phase 5B時点での実装は必須としない。

## Suggested Commit Message

```text
docs: design Program2 dry-run mode for SEALIB import (Phase 5A)
```
