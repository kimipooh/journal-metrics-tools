# convert シート / CONVERT_HEADERS 再設計（Phase 4A）

**作成日**: 2026-06-14 | **ステータス**: 設計提案（未実装・コード変更なし）
**前提**: `docs/program2-resolution-strategy.md`（Phase 3F、(B) 名前再解決方式を正式採用）
**対象**: `journal_metrics.py` の `CONVERT_HEADERS` / `convert` シート / Program2向けTSV出力列

> 本書は **列構成の設計提案のみ**。`convert`コマンド・TSV出力・Program2のいずれも実装しない。CONVERT_HEADERSの更新（コード反映）は本書の対象外（Phase 4Bで実施）。

---

## 0. 決定事項（要約）

- 新 `CONVERT_HEADERS` 案（10列・順序固定）:
  ```
  main_row_id, metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note, convert_status
  ```
- `convert`シートは **`ref_id`/`ref_name`を持たない**。Program2が投入時点のSEALIB DBで再解決し、自ら確定する。
- `metric_country`は`journal.raw_json`内のcandidate `country`（adapter contract §4.1。例: SINTAなら`"ID"`）から取得し、SEALIB `header.country`（LCコード）は使わない。
- `note`は`external_journal_id`/`affiliation`/`eissn`等を`key=value; key=value`形式で集約する（raw_json生ダンプは行わない）。
- Program2向けTSVは、`convert_status=="ready"`の行から`metric_source`〜`note`の8列（中央8列）をそのまま射影出力する。

---

## 1. 現行状況の確認

### 1.1 `docs/rebuild-plan.md` §4 の convert構成（現行案）

```
id, journal_type, grade, external_journal_id, profile_url, journal_name, affiliation, note, convert_status
```

### 1.2 `journal_metrics.py` の `CONVERT_HEADERS`（現行実装）

```python
CONVERT_HEADERS = [
    "id", "journal_type", "grade", "external_journal_id",
    "profile_url", "journal_name", "affiliation", "note", "convert_status",
]
```

`rebuild-plan.md` §8 の `convert → journal_metrics` マッピング（`id→ref_id`, `journal_name→ref_name`等）はこの現行構成を前提にしたもので、(A) 直結方式の想定だった。

### 1.3 Phase 3F方針（前提）

`docs/program2-resolution-strategy.md` で (B) 名前再解決方式が正式採用された。要点:

- `convert`は`ref_id`/`ref_name`を確定しない。
- Program2が投入時点の`header`を`sealib_name`/`sealib_o_name`で再解決し、`ref_id`=解決後`header.id`、`ref_name`=解決後`header.name`を自ら設定する。
- `sealib_id`は補助（0件時fallback・複数候補disambiguation・名前不一致warning）。

本書はこの方針に基づき、`CONVERT_HEADERS`を再設計する。

---

## 2. 新 `CONVERT_HEADERS` 案

```
main_row_id, metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note, convert_status
```

中央8列（`metric_source`〜`note`）は、legacy `metrics_excel.py export`のTSV列順（`metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note`、README.md「Legacy / Previous workflow Behavior」参照）および sealib `journal-metrics-semi-auto-design.md` §8 が定義する Program2向けTSV列順と**完全に一致させる**。これにより、TSV出力時の列並び替えが不要になる（§9）。

### 旧→新 対応表

| 旧 `CONVERT_HEADERS` | 新での扱い |
| --- | --- |
| `id` | `sealib_id`へ転換（補助。`ref_id`への直結はしない） |
| `journal_type` | `metric_source`へ改名（`journal_metrics`列名と1:1対応） |
| `grade` | 維持 |
| `external_journal_id` | 削除。`note`集約候補（§6） |
| `profile_url` | `url`へ改名（`journal_metrics`列名と1:1対応） |
| `journal_name` | 削除。(B)では`ref_name`に使わない。`note`集約候補として検討可（§6） |
| `affiliation` | 削除。`note`集約候補（§6） |
| `note` | 維持（内容・書式は§6で変更） |
| `convert_status` | 維持 |
| （新規） | `main_row_id` — `main`シート行へのトレーサビリティ参照（`journal.main_row_id`と同方式） |
| （新規） | `sealib_name` — Program2の主照合キー（必須） |
| （新規） | `sealib_o_name` — Program2のfallback照合キー（任意） |
| （新規） | `metric_country` — 指標ソース側国コード（必須） |

---

## 3. 各列の整理

| 列 | 意味 | 必須/任意 | 生成元 | Program2での使われ方 | `journal_metrics`対応列 | REST API公開 |
| --- | --- | --- | --- | --- | --- | --- |
| `main_row_id` | この行の元になった`main`シート行（Excel行番号）への参照 | 必須 | convert生成時に対象`main`行のExcel行番号を設定 | 使わない（TSVに出力しない） | なし | されない |
| `metric_source` | 指標ソース識別子（例: `SINTA`） | 必須 | `journal.journal_type` | `DELETE FROM journal_metrics WHERE metric_source=:src`のスコープ指定＋INSERT値 | `metric_source` | される（`source`） |
| `metric_country` | 指標ソース側の国コード（`header.country`とは別符号系） | 必須 | `journal.raw_json`内candidate `country`（§5） | INSERT値 | `metric_country` | される（`country`） |
| `sealib_name` | SEALIB `header.name`照合用の名称 | 必須 | `main.name`（enrich-dbで補完される場合あり） | `header.name`との完全一致検索（主キー） | なし（`ref_name`はProgram2が解決後`header.name`から設定） | されない |
| `sealib_o_name` | SEALIB `header.o_name`照合用の名称（fallback） | 任意 | `main.o_name` | `sealib_name`で0件/複数件時のfallback完全一致検索 | なし | されない |
| `sealib_id` | SEALIB `header.id`の参照値（補助） | 任意 | `main.id`（enrich-dbで補完） | 0件時fallback照合（`WHERE id=:sealib_id`）、複数候補disambiguation、名前不一致warningのトリガー | なし（`ref_id`はProgram2が解決後`header.id`から設定。直結しない） | されない |
| `grade` | 正規化済み評価/等級 | 任意 | `journal.grade`（fetch-journal側で`journal_type`別正規化済み） | INSERT値 | `grade` | される（`grade`） |
| `url` | プロフィール/詳細ページURL | 任意 | `journal.profile_url` | INSERT値 | `url` | される（`url`） |
| `note` | 集約された補足情報（固定書式、§6） | 任意 | `journal.external_journal_id` / `journal.affiliation` / `main.eissn` 等から生成（Phase 4B） | INSERT値 | `note` | される（`note`） |
| `convert_status` | convertワークフロー状態（`ready`/`exported`/`imported`/`skipped`） | 必須 | convert生成ロジック（初期値`ready`） | 使わない（TSVに出力しない） | なし | されない |

---

## 4. `ref_id` / `ref_name` の扱い

- `convert`シートは **`ref_id`/`ref_name`列を持たない**（上記10列に含まれない）。
- Program2が投入時点のSEALIB DBで`sealib_name`/`sealib_o_name`を使い`header`を完全一致再解決する。
- `ref_id` = 解決後の`header.id`
- `ref_name` = 解決後の`header.name`
- `sealib_id`は0件時fallback・複数候補disambiguation・名前不一致warning用の補助情報であり、`ref_id`へ直結しない。

詳細フローは`docs/program2-resolution-strategy.md` §2.1（sealib `journal-metrics-semi-auto-design.md` §6.5 原典）を参照。

---

## 5. `metric_country` の扱い

- `journal_metrics.metric_country`は REST API `?include=metrics`で`country`として公開される（`docs/sealib-api-oai-compatibility-audit.md` §2.3）。
- `metric_country`は**指標ソース側の国コード**（例: SINTAの`country="ID"`、adapter contract §4.1のcandidate `country`フィールド）であり、SEALIB `header.country`（**LCコード**。例: Indonesia = `IO`）とは**異なる符号系**。
- **`header.country`を変換なしに`metric_country`へコピーしない**。
- **値の出どころ（Phase 4A決定）**: `journal.raw_json`に保存されているcandidateの`country`フィールド（adapter contract §4.1）をconvert生成時（Phase 4B）に取り出し、`convert.metric_country`へ設定する。`JOURNAL_HEADERS`への`country`列追加は本書では行わない（`raw_json`から取得可能なため）。
- adapterが`country`を返さない場合（`null`）の扱い（空欄のままにするか、`convert_status`を`needs_review`相当にするか）はPhase 4Bで検討する。

---

## 6. `note` 集約フォーマット（提案）

`journal_metrics.note`はREST APIで公開される唯一の自由記述フィールドであるため、**固定書式・機械的にパース可能な形**とし、`raw_json`の生ダンプは行わない。

### 6.1 集約候補キー

| キー | 出どころ | 必須/任意 |
| --- | --- | --- |
| `external_id` | `journal.external_journal_id` | 任意（値があれば含める） |
| `affiliation` | `journal.affiliation` | 任意 |
| `eissn` | `main.eissn` | 任意 |
| `external_name` | `journal.journal_name`（候補側名称。`sealib_name`と大きく異なる場合のみ含めることを想定） | 任意・Phase 4Bで採否確定 |

### 6.2 書式（提案）

```
key=value; key=value; ...
```

- 区切り文字: `; `（セミコロン+半角スペース）
- 値が`null`/空文字のキーは**含めない**（空の`key=`は出力しない）
- すべてのキーが空の場合、`note`全体を空文字とする
- エンコーディング: UTF-8テキスト（JSON化しない）

**例**:
```
external_id=12345; affiliation=Universitas Indonesia; eissn=8765-4321
```

最終的なキー集合・`external_name`の採否・エスケープ規則（値に`;`や`=`を含む場合の扱い）はPhase 4Bで確定する。

---

## 7. `journal` → `convert` 生成ルール

| `journal.fetch_status` | 変換可否 | 説明 |
| --- | --- | --- |
| `ok`（候補1件） | 変換対象 | `convert`行を自動生成可能。`convert_status="ready"` |
| `multiple`（候補複数） | 人によるレビュー後のみ | 複数`journal`行のうちどれを採用するか人が選ぶまで変換しない |
| `none` | 変換しない | 候補データなし |
| `error` | 変換しない | 取得失敗。再取得が必要 |

### 7.1 `main.status` / `journal.fetch_status` / `convert_status` の関係

- `main.status`: `fetch-journal`実行後、`MAIN_STATUS_BY_ENVELOPE_STATUS`（`journal_metrics.py`）により`fetched`/`multiple_candidates`/`not_found`/`adapter_error`が設定される。convert生成後に`main.status`を`converted`へ更新するか（`docs/rebuild-plan.md` §4の語彙案に`converted`あり）はPhase 4Bで検討。
- `journal.fetch_status`: 上表の通り、convert対象選別の主条件。
- `convert_status`: 生成後のワークフロー状態（`ready`/`exported`/`imported`/`skipped`）。

### 7.2 `fetch_status == "multiple"` 時の選択メカニズム

`fetch_status == "multiple"`の場合、複数`journal`行から1件を選ぶ人手の判断が必要になる。本書では`CONVERT_HEADERS`への`selected`列追加は**採用しない**（§7.3）。代わりに、`JOURNAL_HEADERS`へ`selected`（1/0）相当の列を追加する案をPhase 4Bの検討候補として記載する（`CONVERT_HEADERS`のスコープ外）。

### 7.3 検討した列・採否（タスク指定の「必要に応じて検討」項目）

| 候補列 | 採否 | 理由 |
| --- | --- | --- |
| `external_journal_id` | 不採用（convert列としては） | `note`集約候補（§6.1の`external_id`） |
| `external_journal_name` | 不採用 | `note`集約候補（§6.1の`external_name`、Phase 4Bで採否確定） |
| `affiliation` | 不採用 | `note`集約候補（§6.1） |
| `eissn` | 不採用 | `note`集約候補（§6.1） |
| `raw_json` | 不採用 | `journal`シートに既存。`note`生ダンプ回避方針と矛盾するため複製しない |
| `selected` | 不採用（convert列としては） | `convert_status`の`ready`/`skipped`で同等の制御が可能。`journal`側への追加はPhase 4Bの別検討事項（§7.2） |
| `source_query` | 不採用 | `main_row_id`経由で`main.journal_name`/`main.name`から追跡可能 |

---

## 8. `enrich-db` との関係

- `sealib_name`/`sealib_o_name`/`sealib_id`の出どころは`main.name`/`main.o_name`/`main.id`。これらが空の場合、`enrich-db`（`docs/rebuild-plan.md` §6 Phase 4）がSEALIB DBから補完する。
- `enrich-db`は**補助工程**であり、`sealib_*`列を埋めることが役割。`ref_id`/`ref_name`の最終的な参照整合性保証は`enrich-db`ではなく**Program2が投入時点に担う**（`docs/program2-resolution-strategy.md` §7、`docs/rebuild-plan.md` §8.1）。
- したがって、`enrich-db`実行前でも`sealib_name`（`main.name`）が入力済みであれば`convert`行の生成自体は可能。`sealib_o_name`/`sealib_id`が空でもProgram2側のfallback/disambiguationが機能しない場合があるだけで、`convert`生成のブロッカーにはしない。

---

## 9. Program2向けTSV出力列

### 9.1 列構成

```
metric_source  metric_country  sealib_name  sealib_o_name  sealib_id  grade  url  note
```

`convert`シートの中央8列（`metric_source`〜`note`）と**完全に同じ列・同じ順序**。`main_row_id`（先頭）と`convert_status`（末尾）はTSVに出力しない。

### 9.2 出力対象行

`convert_status == "ready"`の行のみを出力する（legacy `export`が`confirmed==1`の行のみを出力していたのと同様の絞り込み）。

### 9.3 convertシートとの関係

- 列構成を同一にしたため、TSV出力は「対象行のフィルタ＋`main_row_id`/`convert_status`の2列を除いた射影」のみで済み、**並び替えや値変換は不要**。
- 出力後、対象行の`convert_status`を`exported`へ更新する（Phase 4B以降）。

---

## 10. 非対象（本フェーズで行わないこと）

- `convert`コマンドの実装
- `CONVERT_HEADERS`のコード反映・`template`コマンドの更新
- Program2（`03-2-import-metrics.php`）の実装
- TSV出力の実装
- SEALIB DBへの書き込み・`header`メタ情報の更新
- 本番データの投入

---

## 11. Phase 4Bへの引き継ぎ（概要）

詳細は `.codex/tasks/phase4a-convert-sheet-redesign.md` を参照。概要:

- `journal_metrics.py`の`CONVERT_HEADERS`を本書§2の10列へ更新
- `template`コマンドが生成する`convert`シートのヘッダを同期
- `docs/rebuild-plan.md` §4の convert構成記述を本書の内容に同期
- `convert`生成ロジック（§7のルール）、`note`集約ロジック（§6）、TSV export（§9）はPhase 4B以降で実装

---

## 関連ドキュメント

- `docs/program2-resolution-strategy.md`（Phase 3F。(B)名前再解決方式の正式採用）
- `docs/rebuild-plan.md` §4, §8, §8.1
- `docs/adapter-contract.md` §4.1（candidate `country`フィールド）
- `docs/sealib-api-oai-compatibility-audit.md`（REST API `metrics`公開フィールド）
- sealib `docs/journal-metrics-semi-auto-design.md` §6, §8（Program2 TSV列定義・再解決フロー）
