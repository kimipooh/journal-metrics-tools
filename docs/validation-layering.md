# Program2 TSV 二段階検証の責務分担（Phase 5A-2）

**作成日**: 2026-06-14 | **ステータス**: 責務整理（既存実装の確認＋既存設計のクロスリファレンス。コード変更なし）
**前提**:
- `journal_metrics.py` の `validate-tsv`（実装済み）
- `docs/program2-dry-run-design.md`（Phase 5A、`03-2-import-metrics.php --dry-run`設計）
- `docs/convert-sheet-redesign.md`（Phase 4A、TSV列構成・`note`集約方針）
- `docs/program2-resolution-strategy.md`（Phase 3F、(B) 名前再解決方式）

**対象**: `validate-tsv`コマンドと SEALIB Program2 `--dry-run` の二段階検証の役割分担

> 本書は既存実装（`validate-tsv`）と既存設計（Program2 `--dry-run`）の責務整理のみ。コード変更・DB書き込み・Program2実装は行わない。

---

## 0. 決定事項（要約）

- `validate-tsv` と Program2 `--dry-run` は **TSV検証の二段階** として位置づける。
  - 第1段階（`validate-tsv`）: TSVファイル自体の構造・書式検証。SEALIB DBを見ない。
  - 第2段階（Program2 `--dry-run`）: SEALIB DB（core/ext、read-only）に対するheader解決・整合性検証。
- 両者のチェック範囲は現状 **重複していない**。`validate-tsv`はTSVの「形」を、Program2 `--dry-run`はTSVの「内容とSEALIB DBとの整合性」を検証する。
- 実行順序: `export-tsv` → `validate-tsv` → `03-2-import-metrics.php --dry-run` → `03-2-import-metrics.php`（本番投入）。
- Phase 5Bでは、`validate-tsv`が既に担っている構造チェックをProgram2側へ再実装しない。Program2は安全のため列存在確認のみ最低限行う。

---

## 1. `validate-tsv` の責務（実装済み: `journal_metrics.py` `validate_tsv_command`, L474-537）

実コードに基づく確認:

- **入力**: `--input <tsv>`（ファイルのみ。SEALIB DBへは一切アクセスしない）
- **ヘッダ行検証**: 1行目が `PROGRAM2_TSV_HEADERS`（8列: `metric_source, metric_country, sealib_name, sealib_o_name, sealib_id, grade, url, note`）と**完全一致**（列名・順序とも）しない場合 → ERROR
- **列数検証**: 各データ行の列数が8でない場合 → ERROR（該当行はそれ以上のチェックをskip）
- **必須項目検証（ERROR）**: `metric_source` / `metric_country` / `grade` のいずれかが空
- **header候補列検証（ERROR）**: `sealib_name` / `sealib_o_name` / `sealib_id` が全て空
- **`note`書式検証（WARNING）**:
  - `{...}` / `[...]` 形式（JSON風）→ WARNING
  - `key=value; key=value...` 形式でない → WARNING
- **DBアクセス**: なし。SEALIB `header` の解決は行わない
- **終了コード**: ERRORが1件以上あれば `SystemExit(1)`（CI/手元確認で利用可能）。WARNINGのみなら0で終了

→ **「TSVファイル単体として well-formed か」を検証する層**。

---

## 2. Program2 `--dry-run` の責務（設計: `docs/program2-dry-run-design.md`）

- **入力**: `validate-tsv`を通過したTSV + SEALIB DB（core/ext、`mode=ro`）
- **`metric_source`ホワイトリスト検証**: `journal-metrics-semi-auto-design.md` §6.3の設定値と照合（`validate-tsv`は非空チェックのみで、値そのものの妥当性は見ない）
- **header再解決**: `sealib_name`/`sealib_o_name`/`sealib_id`から`header`テーブルを名前優先・ID補助で再解決（dry-run設計 §3アルゴリズム）
- **5カテゴリ分類**: `ready_to_insert` / `warning` / `ambiguous` / `unmatched` / `invalid`
- **INSERT予定行生成**: `ready_to_insert`・`warning`について `ref_id` = 解決後`header.id`、`ref_name` = 解決後`header.name` を含む予定行を生成（dry-run設計 §5）
- **レポート出力**: core/ext別の標準出力サマリ＋任意TSVレポート（dry-run設計 §6）
- **DBアクセス**: SELECTのみ。DELETE/INSERT/バックアップ/トランザクションは行わない

→ **「TSVの内容がSEALIB DBの現在の`header`と整合するか」を検証する層**。

---

## 3. 実行順序

```
1. fetch-journal      journal-metrics-tools: SEALIB候補取得
2. convert            journal-metrics-tools: convertシート生成
3. export-tsv         journal-metrics-tools: convert(ready) → Program2 TSV
4. validate-tsv       journal-metrics-tools: TSV構造・書式検証（第1段階、DBなし）
5. --dry-run          SEALIB Program2: header再解決・整合性確認（第2段階、read-only）
6. 本番投入           SEALIB Program2: DELETE+INSERT
```

4→5の順序が重要: `validate-tsv`でERRORになるTSV（列順違い・必須項目欠落等）をそのままdry-runに渡すと、dry-runのパース時点で`invalid`相当の判定が`validate-tsv`と重複して発生する。`validate-tsv`を先に通すことで、dry-runの`invalid`カテゴリは「構造的には正しいが、ホワイトリストやSEALIB DBとの整合性に問題がある行」に絞られる。

---

## 4. 検出する問題の対応表

| 問題例 | 検出層 | 区分 |
| --- | --- | --- |
| ヘッダ行の列名・順序が`PROGRAM2_TSV_HEADERS`と不一致 | validate-tsv | ERROR |
| データ行の列数が8でない | validate-tsv | ERROR |
| `metric_source`が空 | validate-tsv | ERROR |
| `metric_country`が空 | validate-tsv | ERROR |
| `grade`が空 | validate-tsv | ERROR |
| `sealib_name`/`sealib_o_name`/`sealib_id`が全て空 | validate-tsv | ERROR |
| `note`がJSON風（`{...}`/`[...]`） | validate-tsv | WARNING |
| `note`が`key=value; key=value`形式でない | validate-tsv | WARNING |
| `metric_source`がSEALIB側ホワイトリスト外 | Program2 --dry-run | invalid |
| `sealib_name`が`header.name`/`o_name`のどれにも一致せず、`sealib_id`でも解決不可 | Program2 --dry-run | unmatched |
| `sealib_name`/`o_name`が複数`header`候補に一致し`sealib_id`でも絞れない | Program2 --dry-run | ambiguous |
| 1件一致したが`sealib_id`と解決後`header.id`が不一致 | Program2 --dry-run | warning（id不一致） |
| 0件一致だが`sealib_id`で`header`が見つかる（name不一致） | Program2 --dry-run | warning（name不一致） |
| `metric_country`の値自体の妥当性（LCコード等） | （両層とも対象外） | - |

---

## 5. Phase 5Bへの影響

1. **`validate-tsv`ロジックの非重複**: Program2 `--dry-run`は、`validate-tsv`が既にカバーするヘッダ完全一致・列数・必須項目空チェック・`note`書式チェックを再実装しない。
2. **Program2側の最低限チェック**: 安全のため、Program2（dry-run・本番投入とも）はTSVヘッダから`PROGRAM2_TSV_HEADERS`8列が**列順不問で存在するか**のみ確認する（`03-1-import-metrics-sinta.php`の`array_flip`方式）。存在しない場合は処理を中断する。これは「`validate-tsv`を経ていない手編集TSV」に対する最低限の防御であり、`validate-tsv`の厳密な順序チェックを置き換えるものではない。
3. **ホワイトリスト検証はProgram2側の専管**: `metric_source`の許可値リストはSEALIB側設定（`journal-metrics-semi-auto-design.md` §6.3）にあり、journal-metrics-tools側からは見えない。`validate-tsv`は非空チェックのみを担当し、値の妥当性検証はProgram2（dry-run含む）が担当する、という現状の分担を維持する。
4. **Program2の主責務**: header再解決・5カテゴリ分類・INSERT予定行生成・レポート出力（`docs/program2-dry-run-design.md` §3-§6）。
5. 本書の決定は`docs/program2-dry-run-design.md`の既存内容と矛盾しないため、同文書の修正は不要（本書からの参照のみ追加）。

---

## 6. 非対象（本フェーズで行わないこと）

- コード変更（`journal_metrics.py`含む）は行わない。
- SEALIB DBへの書き込みは行わない。
- Program2本体・dry-run CLIの実装は行わない。
- `validate-tsv`の変更は行わない。

---

## 関連ドキュメント

- `docs/program2-dry-run-design.md`（Phase 5A）
- `docs/convert-sheet-redesign.md`（Phase 4A）
- `docs/program2-resolution-strategy.md`（Phase 3F）
- `docs/sealib-api-oai-compatibility-audit.md`（Phase 3E）
- `journal_metrics.py`（`validate_tsv_command` L474-537, `PROGRAM2_TSV_HEADERS` L66-75, `note_looks_like_json`/`note_has_key_value_format` L187-208）
