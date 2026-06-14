# Phase 4A: convert シート / CONVERT_HEADERS 再設計（記録）

## 目的

Phase 3F（`docs/program2-resolution-strategy.md`、(B) 名前再解決方式の正式採用）に基づき、journal-metrics-toolsの`convert`シート列（`CONVERT_HEADERS`）とProgram2向けTSV出力列を再設計し、文書化する。

## 対象

- journal-metrics-tools: `journal_metrics.py`の`CONVERT_HEADERS`、`template`コマンドが生成する`convert`シート（いずれも設計提案のみ、コード変更は行わない）

## 制約

- 本フェーズはコード変更を行わない。
- `convert`コマンド、Program2、TSV出力のいずれも実装しない。
- DB書き込み、`header`メタ情報の更新、本番データ投入を行わない。
- 既存ファイル（`docs/rebuild-plan.md`, `docs/program2-resolution-strategy.md`, `docs/sealib-api-oai-compatibility-audit.md`, `docs/adapter-contract.md`, `README.md`, `journal_metrics.py`, `journal_mapper.py`）は変更しない。

## 必ず読むファイル

- `docs/rebuild-plan.md`
- `docs/program2-resolution-strategy.md`
- `docs/sealib-api-oai-compatibility-audit.md`
- `docs/adapter-contract.md`
- `README.md`
- `journal_metrics.py`
- `journal_mapper.py`
- sealib `docs/journal-metrics-semi-auto-design.md`
- sealib `docs/sealib-journal-metrics-tools-design.md`

## 決定内容（要約）

新`CONVERT_HEADERS`案（10列・順序固定）:

```
main_row_id, metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note, convert_status
```

中央8列（`metric_source`〜`note`）はProgram2向けTSV列順（legacy `export`、sealib `journal-metrics-semi-auto-design.md` §8と同順）と一致させ、TSV出力時の並び替えを不要にした。

詳細・各列の意味/必須任意/生成元/Program2での使われ方/`journal_metrics`対応/REST API公開の整理表、`ref_id`/`ref_name`の扱い、`metric_country`の値の出どころ、`note`集約フォーマット、`journal→convert`生成ルールは`docs/convert-sheet-redesign.md`を参照。

## 検証項目

1. `docs/convert-sheet-redesign.md`が作成されていること。
2. `.codex/tasks/phase4a-convert-sheet-redesign.md`（本ファイル）が作成されていること。
3. (B) 名前再解決方式に整合していること（`ref_id`/`ref_name`をconvertが持たない）。
4. `metric_country`と`header.country`の符号系の違いが明記されていること。
5. `note`集約方針が明記されていること。
6. コード変更がないこと（`journal_metrics.py`等は未変更）。

## Phase 4Bへの引き継ぎ

Phase 4Bで実施すべき最小作業（実装はまだ依頼しない。開始時に個別の`.codex/tasks/phase4b-*.md`を作成する）:

1. **`CONVERT_HEADERS`更新**: `journal_metrics.py`の`CONVERT_HEADERS`を`docs/convert-sheet-redesign.md` §2の10列へ更新する。
2. **`template`コマンド更新**: `build_template_workbook()`が生成する`convert`シートのヘッダが新`CONVERT_HEADERS`に追従していることを確認する（`write_header_sheet(convert, CONVERT_HEADERS)`は定数参照のため自動追従するが、`README_ROWS`等の説明文に列名が含まれる場合は同期する）。
3. **`docs/rebuild-plan.md`との同期**: §4 の convert構成テーブル（現行: `id, journal_type, grade, external_journal_id, profile_url, journal_name, affiliation, note, convert_status`）を新10列に更新し、§8.1からの参照（「§4のconvert列構成…はPhase 4Aで再設計する」）を解消する。
4. **`convert`生成ロジック**: `docs/convert-sheet-redesign.md` §7の`fetch_status`別ルール（`ok`→自動変換対象、`multiple`→人によるレビュー後、`none`/`error`→対象外）に基づく実装はPhase 4B以降。
5. **`note`集約ロジック**: §6の`key=value; key=value`形式（`external_id`/`affiliation`/`eissn`、`external_name`は採否確定）の実装はPhase 4B以降。
6. **`metric_country`抽出ロジック**: `journal.raw_json`からcandidateの`country`を取り出し`convert.metric_country`へ設定する実装はPhase 4B以降。
7. **TSV export**: §9の8列射影・`convert_status=="ready"`フィルタ・出力後の`convert_status`更新（`exported`）はPhase 4C以降。

## Suggested Commit Message

```text
docs: redesign convert sheet / CONVERT_HEADERS for (B) name-resolution (Phase 4A)
```
