# Phase 7A: SINTA adapter 設計（記録）

## 目的

journal-metrics-tools に SINTA を metrics source として接続する前に、既存 `sinta-full-cli-v3` の呼び出し仕様（CLI引数・JSON出力・timeout/error挙動）、旧 `metrics_excel.py` での SINTA 呼び出し実装（subprocess・JSON parse・grade正規化・error handling）、`adapters/sinta.py` の関数仕様案、adapter contract への candidate マッピング、grade/status方針、Phase 7B の最小実装範囲を整理する。

## 対象

- `adapters/sinta.py`（新規作成予定、Phase 7A では未作成）の関数仕様案
- `docs/adapter-contract.md` candidate フィールドへの SINTA マッピング
- SINTA CLI（`sinta-full-cli-v3.py`）の呼び出し仕様
- Phase 7B 実装範囲の定義

## 制約

- 本フェーズはコード変更を行わない。
- `adapters/sinta.py` を実装しない。
- SINTA への本番アクセス・大量取得を行わない。
- Thai Tier adapter を扱わない。
- grade正規化を行わない。
- Program2（`03-2-import-metrics.php`）を変更しない。
- SEALIB DBへの書き込み・本番データ投入を行わない。
- 既存ファイル（`journal_metrics.py`, `journal_mapper.py`, `adapters/mock.py`, `adapters/sealib.py`, 旧 `metrics_excel.py`, `README.md`, 既存 `docs/*.md`）は変更しない。

## 必ず読んだファイル

- `journal_metrics.py`（`query_for_adapter`, `fetch_journal_command`, `MAIN_STATUS_BY_ENVELOPE_STATUS`, `JOURNAL_HEADERS`）
- `docs/adapter-contract.md`（candidate/envelope/status語彙の共通契約）
- `docs/grade-and-source-policy.md`（`metric_source` 役割分類、SINTAをmetrics sourceとする前提）
- `docs/convert-sheet-redesign.md`（`metric_country` の出どころ、`raw_json`経由の `country` 保持）
- `docs/program2-resolution-strategy.md`（(B) 名前再解決方式）
- `README.md`（Phase 3D現状、`search_query`/`journal_name`/`name` の使い分け方針）
- 旧 `metrics_excel.py`（`resolve_adapter_command`, `run_sinta_cli`, `extract_json_payload`, `normalize_candidates`, `normalized_grade`, `add_sinta_args`）
- `adapters/sealib.py`（既存adapterの実装パターン、`db_path is None`→`adapter_error`の前例）
- `adapters/mock.py` / `journal_mapper.py`（candidate→journal行の変換経路）
- `../sinta-full-cli-v3/sinta-full-cli-v3.py`（CLI引数、`BASIC_FIELDS`/`DETAIL_FIELDS`、`search_sinta_journal`、JSON出力・0件時挙動）
- `../sinta-full-cli-v3/README.md`（CLI仕様の文書化状況）
- `../sinta-full-cli-v3/docs/`: 存在しない（確認済み）

## 決定内容（要約）

1. **SINTA CLI 呼び出し仕様**: `-q <query> -m title -f json --fetch-mode basic`。ISSN検索オプションは無い。0件時はstdout空・exit 0（stderrの有無で「0件」と「検索失敗」を区別する必要あり、§1.4）。1件/複数件はJSON配列で返る。全体timeoutはCLI側になく、呼び出し側の `subprocess.run(..., timeout=...)` で制御する（旧既定180s）。
2. **旧呼び出し実装**: `resolve_adapter_command`（スクリプトパス必須・既定値なし）、`run_sinta_cli`（`subprocess.run` + `extract_json_payload`/`normalize_candidates`）、`normalized_grade`（**export時のみ**の正規化、adapterには移植しない）。
3. **実装場所**: `adapters/sinta.py`（新規、`adapters/mock.py`/`adapters/sealib.py`と同パターン）。
4. **関数仕様案**: `fetch_journal(query: str, source: str = "SINTA", command: str | None = None, python: str | None = None, timeout: int = 180) -> dict`。`command`は既定値なし・必須（未指定は`adapter_error`）。`mode`/`fetch_mode`はPhase 7Bでは`"title"`/`"basic"`固定で adapter引数化しない。
5. **query方針**: `query_for_adapter()`（`journal_metrics.py` L193-203）が non-sealib adapter向けに既に `search_query`→`journal_name`フォールバック・`name`フォールバックなしを実装済みであり、SINTA向けの変更は不要。両方空の場合の`main.status`扱い（silent skip vs `adapter_error`）はPhase 7Cの論点として保留。
6. **candidateマッピング**: `journal_id→external_journal_id`, `journal_name→title`, `affiliation→publisher`, `sinta_level→grade`（raw）, `profile_url→url`, `country`は固定`"ID"`, `issn`/`eissn`は basic mode では常に`null`, `note`は Phase 7B では`null`。`"N/A"`は`null`に変換。
7. **grade方針**: raw値（`sinta_level`）をそのまま返す。正規化は行わない。Program2 TSVでのraw/正規化の扱いは後続フェーズ判断。
8. **status変換**: 候補0/1/2+→`not_found`/`fetched`/`multiple_candidates`。CLI失敗・timeout・JSON parse失敗・`command`未指定→`adapter_error`。`journal.fetch_status`対応は既存`FETCH_STATUS_BY_ENVELOPE_STATUS`をそのまま使用。

詳細は `docs/sinta-adapter-design.md` を参照。

## 検証項目

1. `docs/sinta-adapter-design.md` が作成されていること。
2. `.codex/tasks/phase7a-sinta-adapter-design.md`（本ファイル）が作成されていること。
3. SINTA CLI（`sinta-full-cli-v3.py`）の呼び出し仕様（引数・JSON出力・0件/エラー/timeout挙動）が整理されていること。
4. `adapter-contract.md` candidateフィールドへのSINTAマッピングが整理されていること。
5. `fetch_journal` 関数仕様案（シグネチャ・`command`必須・固定コマンド構成）が明記されていること。
6. grade方針（raw値・正規化なし）が明記されていること。
7. status変換ルール（`fetched`/`multiple_candidates`/`not_found`/`adapter_error`）が明記されていること。
8. Phase 7B の最小実装範囲が定義されていること。
9. 既存コードファイル（`journal_metrics.py`, `adapters/*.py`, `journal_mapper.py`, `metrics_excel.py`, `README.md`）が変更されていないこと（コード変更なし）。

## Phase 7Bへの影響

- `adapters/sinta.py` を新規作成し、`docs/sinta-adapter-design.md` §4・§6・§8 に基づき `fetch_journal()` を実装する。
- `command`未指定時の`adapter_error`、CLI失敗/timeout/JSON parse失敗の`adapter_error`化、候補数による`fetched`/`multiple_candidates`/`not_found`判定を実装する。
- 実ネットワークに依存しない単体テスト（スタブスクリプト or `subprocess.run`モック）を追加する。
- `journal_metrics.py` への `--adapter sinta` 接続は Phase 7C 以降（本タスクの対象外）。
- Phase 7Cで`query`が空の場合の`main.status`扱い（silent skip vs `adapter_error`、`docs/sinta-adapter-design.md` §5）を判断する。

## Suggested Commit Message

```text
docs: define Phase 7A SINTA adapter design
```
