# Program2 dry-run 設計（Phase 5A）

**作成日**: 2026-06-14 | **ステータス**: 設計提案（未実装・コード変更なし）
**前提**: `docs/program2-resolution-strategy.md`（Phase 3F、(B) 名前再解決方式）、`docs/convert-sheet-redesign.md`（Phase 4A、TSV列構成）
**対象**: SEALIB側 Program2（`03-2-import-metrics.php`）の `--dry-run` モード仕様

> 本書は **dry-run仕様の設計提案のみ**。Program2本体・dry-run CLIのいずれも実装しない。SEALIB DBへの書き込みは行わない。

---

## 0. 決定事項（要約）

- dry-runは sealib `journal-metrics-semi-auto-design.md` §6 が計画する `03-2-import-metrics.php` の `--dry-run` モードとして設計する（新規ツールは作らない）。
- 入力TSVは `docs/convert-sheet-redesign.md` §9 の8列（`metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note`）。
- header解決ルールは §6.5「名前優先・ID補助」を、5つの出力カテゴリ（`ready_to_insert` / `warning` / `ambiguous` / `unmatched` / `invalid`）に分類するアルゴリズムとして具体化する。
- `ready_to_insert`と`warning`は **INSERT予定行を生成する**（`warning`は採用するが注記付き）。`ambiguous`/`unmatched`/`invalid`はスキップ・ログのみ。
- dry-runはSELECTのみ。DELETE/INSERT/バックアップ/トランザクションは行わない。

---

## 1. dry-run の目的

Program2本番投入（DELETE+INSERT、`journal-metrics-semi-auto-design.md` §6.7以降）の前に、以下を **read-only** で事前確認できるようにする。

1. 入力TSVを読み込む。
2. SEALIB DB（core / ext）を `mode=ro` で開く（旧 `read_sealib_rows`、`03-1-import-metrics-sinta.php`のPDO接続をread-only化）。
3. `sealib_name` / `sealib_o_name` / `sealib_id` で `header` を再解決する（§3）。
4. `journal_metrics` へのINSERT予定行（§5）を行ごとに生成する。
5. 投入予定行数、`unmatched` / `ambiguous` / `warning` 件数をレポートする（§6）。
6. **実際のDB書き込み（DELETE/INSERT/バックアップ）は行わない**。

dry-runの目的は、TSV側（journal-metrics-toolsの`convert`シート/export結果）の不整合を、本番投入の前にcore/ext両DBに対して検出し、修正のフィードバックループを可能にすることである。

---

## 2. 入力TSV仕様の確認

`docs/convert-sheet-redesign.md` §9 で定義した8列をそのまま使用する。

```
metric_source  metric_country  sealib_name  sealib_o_name  sealib_id  grade  url  note
```

| 列 | 必須/任意 | dry-runでの扱い |
| --- | --- | --- |
| `metric_source` | 必須 | ホワイトリスト検証対象（`journal-metrics-semi-auto-design.md` §6.3）。不正値は`invalid` |
| `metric_country` | 任意 | そのままINSERT予定行へ転記（値の妥当性検証は本書スコープ外） |
| `sealib_name` | 必須 | header解決の主キー（§3）。空は`invalid` |
| `sealib_o_name` | 任意 | header解決の副キー（§3） |
| `sealib_id` | 任意 | header解決の補助（fallback / disambiguation / mismatch検出、§3） |
| `grade` | 任意 | そのまま転記 |
| `url` | 任意 | そのまま転記 |
| `note` | 任意 | そのまま転記 |

- ヘッダ行必須・列順は任意（`03-1-import-metrics-sinta.php`同様、`array_flip`によるヘッダ名ベース判定）。
- UTF-8（BOM除去）、タブ区切り、行末の列数不足はパディング（`03-1`と同方式）。
- 空行はスキップ（`skipped`としてカウント、`invalid`には含めない）。

---

## 3. header解決ルール（名前優先・ID補助）

`journal-metrics-semi-auto-design.md` §6.5を、5カテゴリ分類アルゴリズムとして具体化する。

### 3.1 アルゴリズム

```
1. 行バリデーション
   - metric_source がホワイトリストに無い → invalid
   - sealib_name が空 → invalid
   （いずれかに該当した行はheader解決を行わず終了）

2. 候補集合の取得（完全一致）
   candidates = SELECT id, name, o_name FROM header
                WHERE name = :sealib_name OR o_name = :sealib_name
   sealib_o_name が非空の場合、
                  OR name = :sealib_o_name OR o_name = :sealib_o_name
                も条件に加える
   id で重複除去

3. candidates の件数で分岐

   [1件]
     candidate = candidates[0]
     - sealib_id が非空 かつ candidate.id != sealib_id
         → warning（id不一致。candidate を採用しTSVのsealib_idとの不一致を記録）
     - それ以外
         → ready_to_insert

   [複数件]
     - sealib_id が非空 かつ candidates のいずれかの id と一致
         → ready_to_insert（resolution_method = disambiguated_by_sealib_id）
     - それ以外
         → ambiguous（スキップ・ログ）

   [0件]
     - sealib_id が非空
         fallback = SELECT id, name FROM header WHERE id = :sealib_id
         - fallback が見つかる
             → warning（name不一致。fallback を採用し名前不一致を記録）
         - fallback が見つからない
             → unmatched（スキップ・ログ）
     - sealib_id が空
         → unmatched（スキップ・ログ）
```

### 3.2 想定ケースとカテゴリ対応表

| # | 想定ケース | candidates件数 | sealib_id状況 | カテゴリ |
| --- | --- | --- | --- | --- |
| 1 | `sealib_name`で1件一致 | 1 | 未指定 or 一致 | `ready_to_insert` |
| 2 | `sealib_o_name`で1件一致 | 1 | 未指定 or 一致 | `ready_to_insert` |
| 3 | 1件一致だが`sealib_id`と不一致 | 1 | 不一致 | `warning`（id不一致） |
| 4 | `name`/`o_name`で複数一致、`sealib_id`で1件に絞れる | 複数 | 候補内に存在 | `ready_to_insert`（disambiguated_by_sealib_id） |
| 5 | `name`/`o_name`で複数一致、`sealib_id`で絞れない | 複数 | 候補内に無い/空 | `ambiguous` |
| 6 | 0件、`sealib_id`未指定 | 0 | 空 | `unmatched` |
| 7 | 0件だが`sealib_id`が`header.id`に存在 | 0 | 一致（fallback成功） | `warning`（name不一致） |
| 8 | `sealib_id`を指定したが該当`header.id`が存在しない | 0 | 不一致（fallback失敗） | `unmatched` |
| 9 | 必須列欠落・`metric_source`不正・`sealib_name`空 | - | - | `invalid` |

---

## 4. 出力カテゴリ定義

| カテゴリ | 意味 | INSERT予定行を生成するか |
| --- | --- | --- |
| `ready_to_insert` | `header`を一意に解決できた（id不一致等の懸念なし） | する |
| `warning` | 採用するが、TSVの`sealib_id`と解決結果の間に不一致があり注記が必要 | する（注記付き） |
| `ambiguous` | `name`/`o_name`で複数候補に一致し、`sealib_id`でも一意に絞れない | しない（スキップ・ログ） |
| `unmatched` | `name`/`o_name`/`sealib_id`のいずれでも`header`を解決できない | しない（スキップ・ログ） |
| `invalid` | TSV行自体が無効（必須列欠落・ホワイトリスト外・`sealib_name`空） | しない（スキップ・ログ） |

`ready_to_insert` + `warning` の合計が、本番投入時に実際にINSERTされる予定の行数に相当する。

---

## 5. INSERT予定行の形

`01-3-create-metrics-table.php`の`journal_metrics`スキーマ（`mid, ref_id, ref_name, metric_source, metric_country, grade, url, note, imported_at`）に対応する。

```json
{
  "ref_id": "<解決後 header.id>",
  "ref_name": "<解決後 header.name>",
  "metric_source": "<TSV.metric_source>",
  "metric_country": "<TSV.metric_country>",
  "grade": "<TSV.grade>",
  "url": "<TSV.url>",
  "note": "<TSV.note>",
  "imported_at": null
}
```

- `ref_id` = §3で解決した`header.id`（TSVの`sealib_id`をそのまま使わない）。
- `ref_name` = §3で解決した`header.name`（TSVの`sealib_name`をそのまま使わない）。
- `mid`はAUTOINCREMENTのためdry-runでは生成しない。
- `imported_at`は**実投入時にProgram2が付与**する（dry-runでは`null`または未設定のまま表示。現在時刻のプレビューはしない）。
- 対応するINSERT文（本番、参考）:
  ```sql
  INSERT INTO journal_metrics
      (ref_id, ref_name, metric_source, metric_country, grade, url, note, imported_at)
  VALUES
      (:ref_id, :ref_name, :metric_source, :metric_country, :grade, :url, :note, :imported_at)
  ```
  現行`03-1-import-metrics-sinta.php`は`metric_source`/`metric_country`を`'SINTA'`/`'ID'`に固定し`note`列をINSERTしていないが、新Program2はTSVの`metric_source`/`metric_country`/`note`を使用する（`docs/program2-resolution-strategy.md`参照）。

---

## 6. dry-run レポート形式

最小実装は **標準出力サマリ + 任意のTSVレポート** で十分とする。JSONレポートは本フェーズでは不要（将来、機械可読な後処理が必要になった場合に検討）。

### 6.1 標準出力サマリ（例）

```
[ext] /path/to/sqlite_library_seas_ext.db
  Total rows:        120
  ready_to_insert:   105
  warning:             4
  ambiguous:           3
  unmatched:           6
  invalid:             2
  -> Planned INSERT (ready_to_insert + warning): 109

[core] /path/to/sqlite_library_seas.db
  Total rows:        120
  ready_to_insert:    98
  warning:             4
  ambiguous:           3
  unmatched:          13
  invalid:             2
  -> Planned INSERT (ready_to_insert + warning): 102
```

### 6.2 TSVレポート（任意・推奨）

行ごとの詳細を機械可読に出力する。列構成案:

```
line_no  sealib_name  sealib_o_name  sealib_id  metric_source  category  resolved_ref_id  resolved_ref_name  message
```

- `category`: §4の5カテゴリ。
- `resolved_ref_id` / `resolved_ref_name`: `ready_to_insert`/`warning`のみ値を持つ。
- `message`: `warning`/`ambiguous`/`unmatched`/`invalid`時の人間向け説明（例: `id mismatch: TSV sealib_id=001TH00099 but resolved header.id=001TH00042`）。

---

## 7. core/ext 両DBへの適用方針

- dry-runは **DBごとに独立実行**する（`03-1-import-metrics-sinta.php`の`$db_targets = {"core": ..., "ext": ...}`と同様、それぞれ`mode=ro`で開く）。
- `header`の内容・`id`はcore/extで一致しない場合がある（extは増補版で対象誌が多い）。そのため、同一TSV行でもcore/extで解決結果（カテゴリ・`ref_id`/`ref_name`）が異なり得る。
- 本番投入時は、`01-3-create-metrics-table.php`同様 core/ext **両方**へ同じTSVを投入する設計になる可能性が高い（スキーマが共通のため）。
- dry-runでは、§6.1のサマリをcore/extそれぞれ独立して出力することを基本とし、**同一TSV行でcore/ext間の解決結果（カテゴリやref_id）が異なる行を「ext/core差分」として検出・レポートする機能をPhase 5B以降の検討対象**とする（本書では仕様の方向性のみ示し、実装詳細は確定しない）。

---

## 8. 非対象（本フェーズで行わないこと）

- SEALIB DBへの書き込み（DELETE/INSERT/バックアップ/トランザクション）は行わない。dry-runはSELECTのみ。
- REST API v1 / OAI-PMH 2.0 の変更は行わない（`docs/sealib-api-oai-compatibility-audit.md`の調査結果どおり、journal_metrics投入方式の変更はAPI仕様自体に影響しない）。
- journal-metrics-tools側のExcel（`main`/`journal`/`convert`）は変更しない。
- Program2本体（DELETE+INSERT実装）・dry-run CLIの実装は行わない。
- 本番データの投入は行わない。

---

## 9. Phase 5Bへの引き継ぎ（概要）

詳細は `.codex/tasks/phase5a-program2-dry-run-design.md` を参照。概要:

1. **dry-run CLI実装**: `03-2-import-metrics.php --dry-run`として、§1の手順（TSV読み込み→header解決→レポート→終了。バックアップ/トランザクション/DELETE/INSERTの手前で停止）を実装する。
2. **read-only SQLite接続**: `mode=ro`のPDO/SQLite接続（`03-1`の接続をread-only化）。
3. **TSV parse**: §2の8列をヘッダ名ベースで判定（`03-1`の`array_flip`方式を流用）。
4. **header解決ロジック**: §3のアルゴリズムを実装（candidates取得・件数分岐・5カテゴリ判定）。
5. **レポート出力**: §6の標準出力サマリ（必須）+ TSVレポート（任意）。
6. **metric_sourceホワイトリスト**: `journal-metrics-semi-auto-design.md` §6.3の設定値をdry-runでも適用。

---

## 関連ドキュメント

- `docs/program2-resolution-strategy.md`（Phase 3F。(B)名前再解決方式の正式採用、header解決フローの原典）
- `docs/convert-sheet-redesign.md`（Phase 4A。TSV列構成、`note`集約方針）
- `docs/sealib-api-oai-compatibility-audit.md`（Phase 3E。REST API/OAI-PMHへの影響なしの確認）
- `docs/rebuild-plan.md` §8.1
- sealib `docs/journal-metrics-semi-auto-design.md` §6（Program2設計、ref_id再解決フロー原典）、§8（TSV列定義）
- sealib `admin/import-data-ext/03-1-import-metrics-sinta.php`（現行(A)実装、INSERT文・DB接続方式の参考）
- sealib `admin/import-data-ext/01-3-create-metrics-table.php`（`journal_metrics`スキーマ定義）
