# Phase 3F: Program2 投入方式 設計判断（記録）

## 目的

Phase 3E（`docs/sealib-api-oai-compatibility-audit.md`）の調査結果を受けて、journal-metrics-tools の `convert` / `enrich-db`、および SEALIB側 Program2（`journal_metrics`投入）の方式について、(A) 直結方式 と (B) 名前再解決方式 のどちらを採用するかを確定し、文書化する。

## 対象

- journal-metrics-tools: `convert` / `enrich-db`（いずれも未実装。本フェーズは設計判断のみ）
- SEALIB: Program2（`03-2-import-metrics.php`、未実装。設計上の前提として参照のみ）

前提:

- (A) 直結方式 = 現行 `03-1-import-metrics-sinta.php` 的に、`ref_id`/`ref_name`をTSVの値そのまま投入する方式
- (B) 名前再解決方式 = `journal-metrics-semi-auto-design.md` §6 が計画する、投入時点の`header`を名前で再解決して`ref_id`/`ref_name`を導出する方式

## 制約

- 本フェーズはコード変更を行わない。
- DB書き込み、`header`メタ情報の更新、本番データ投入を行わない。
- `convert` / `enrich-db` / Program2 の実装は行わない。
- 以下の既存ファイルは変更しない: `docs/sealib-api-oai-compatibility-audit.md`, `docs/rebuild-plan.md`, `docs/adapter-contract.md`, `README.md`, `journal_metrics.py`, `adapters/sealib.py`, sealib側ドキュメント一式。

## 必ず読むファイル

- `docs/sealib-api-oai-compatibility-audit.md`（Phase 3E成果物。本判断の直接の前提）
- `docs/rebuild-plan.md`
- `docs/adapter-contract.md`
- `README.md`
- `journal_metrics.py`
- `adapters/sealib.py`
- sealib `docs/journal-metrics-semi-auto-design.md`
- sealib `docs/sealib-journal-metrics-tools-design.md`
- sealib `README.md`
- sealib `CLAUDE.md`

## 決定内容（要約）

- **採用**: (B) 名前再解決方式
- **不採用**: (A) 直結方式
- 不採用理由・各種影響整理・次フェーズ提案の詳細は `docs/program2-resolution-strategy.md` を参照。

### (B) の要点

- convertは`sealib_name`/`sealib_o_name`/`sealib_id`（補助）を保持し、Program2に渡す。
- Program2は投入時点の`header`をTSVの`sealib_name`/`sealib_o_name`で完全一致再解決する。
- `ref_id`/`ref_name`はProgram2が解決後の`header.id`/`header.name`から算出する（TSVには含めない）。
- `sealib_id`は0件時fallback／複数候補disambiguation／名前不一致warning用の補助情報。

### (A) を不採用とする理由（要約）

- `convert.id`→`ref_id`直結は、フルビルドで`header.id`が変わると`ref_id`が孤立する。
- `convert.journal_name`→`ref_name`直結は、外部ソース側の名称をSEALIB側の現在名として扱うことになり、(B)の意味と矛盾する。
- `ref_id`孤立時、REST API `?include=metrics`は`metrics: []`を返すのみでエラーにならず、運用上気づきにくい。

## 検証項目

1. `docs/program2-resolution-strategy.md` が存在し、(B) 名前再解決方式が採用方針として明記されていること。
2. `.codex/tasks/phase3f-program2-resolution-strategy.md`（本ファイル）が存在すること。
3. (A) 直結方式を不採用とする理由が明文化されていること。
4. convertシート/`CONVERT_HEADERS`の列候補（`sealib_name`/`sealib_o_name`/`sealib_id`/`metric_source`/`metric_country`/`grade`/`url`/`note`）が整理されていること。
5. REST API v1 / OAI-PMH 2.0 への影響が整理されていること。
6. 上記「制約」に列挙した既存ファイルが変更されていないこと（コード変更なし）。

## 次アクション（概要・実装はまだ依頼しない）

- **Phase 4A**: convertシート / `CONVERT_HEADERS`再設計（`docs/program2-resolution-strategy.md` §4の対比表を起点に列構成を確定）
- **Phase 4B**: convert生成ロジック実装
- **Phase 4C**: Program2向けTSV export実装
- **Phase 5**: SEALIB側 Program2（`03-2-import-metrics.php`）実装/調整（sealib repoでの別タスク）

各フェーズの実装指示は、開始時に個別の `.codex/tasks/phase4*-*.md` として別途作成する。

## Suggested Commit Message

```text
docs: adopt Program2 name-resolution strategy (Phase 3F)
```
