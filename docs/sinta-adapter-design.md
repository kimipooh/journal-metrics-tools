# SINTA adapter 設計

**作成日**: 2026-06-15 | **ステータス**: 設計メモ（v1.0.0 で実装済み）
**前提**:
- `docs/adapter-contract.md`（adapter 共通契約）
- `docs/grade-and-source-policy.md`（`metric_source` 役割分類・grade必須方針）
- `journal_metrics.py`（`query_for_adapter`, `fetch_journal_command`, `MAIN_STATUS_BY_ENVELOPE_STATUS`）
- `adapters/sealib.py`（既存 adapter の実装パターン）
- `../sinta-full-cli-v3/sinta-full-cli-v3.py`, `../sinta-full-cli-v3/README.md`

**対象**: `adapters/sinta.py` の関数仕様・候補マッピング・status 変換・実装範囲

> 本書は **設計のみ**。SINTA への本番アクセスは行わない。
>
> **v1.0.0 注記**: 現行実装は `journal_metrics.py` / `journal_mapper.py` / `adapters/` である。

---

## 0. 決定事項（要約）

- `adapters/sinta.py` に `fetch_journal(query, source="SINTA", command=None, python=None, timeout=180) -> dict` を実装する。
- 内部では `[python or sys.executable, command, "-q", query, "-m", "title", "-f", "json", "--fetch-mode", "basic"]` を `subprocess.run(..., timeout=timeout)` で呼び出す。`mode`/`fetch_mode` は固定値とし、adapter 引数として公開しない。
- `command` は **既定値なし・明示必須**。未指定時は `adapter_error`（`adapters/sealib.py` の `db_path is None` と同方針）。
- SINTA adapter は `query` を `main.search_query`（空なら `main.journal_name`）から得る前提とする。`main.name` への fallback は行わない。これは `journal_metrics.py` の既存 `query_for_adapter()` がすでに保証しており、SINTA 用の変更は不要。
- `country` は固定値 `"ID"` を返す（`docs/adapter-contract.md` §5.1/5.2 の SINTA 例と一致）。
- `grade` は SINTA の `sinta_level` raw 値（例: `"S1 Accredited"`）をそのまま返す。正規化は行わない（adapter contract §3 / `docs/grade-and-source-policy.md` §7 と一致）。
- 通常検索は `--fetch-mode basic`（既定）で行う。title 完全一致候補が2件以上あり、`main.issn` / `main.eissn` が存在し、basic 結果だけでは ISSN 補助照合で一意化できない場合に限り、`--fetch-mode detail` を追加実行して `p_issn` / `e_issn` を取得する。
- status 変換は `docs/adapter-contract.md` §4.4 に準拠する。候補数 0件は `not_found`、1件は `fetched`、複数件は原則 `multiple_candidates` とする。ただし複数候補のうち、正規化後の候補 title が正規化後の検索キーと完全一致するものが1件だけの場合は、その1件だけを `fetched` として返す。title 完全一致候補が2件以上ある場合は、`main.issn` / `main.eissn` と候補 `p_issn` / `e_issn` の ISSN 正規化値を照合し、一意に一致した場合だけ `fetched` とする。CLI失敗・timeout・JSON parse失敗・`command`未指定は `adapter_error` とする。detail 取得のみの失敗は検索自体の失敗ではないため、`adapter_error` にせず basic 検索結果の `multiple_candidates` を保持する。
- `fetch-journal --adapter sinta --update` により既存 fetched/not_found/multiple_candidates 行も再取得できる。既存 `journal` 行の置換は adapter ではなく `journal_metrics.py` 側で行い、同じ `main_row_id` かつ `journal_type=SINTA` の行だけを削除してから新しい envelope を書き込む。SEALIB や他 adapter の journal 行は保持する。

---

## 1. sinta-full-cli-v3 の利用方法

### 1.1 CLI コマンドと入力パラメータ

`sinta-full-cli-v3.py` の `argparse` 定義（L329-348）:

| オプション | 必須/既定 | 説明 |
| --- | --- | --- |
| `-q` / `--query` | **必須** | 検索キーワード（自由文字列） |
| `-m` / `--mode` | 既定 `title` | `title`（SINTA検索ページの `search=1`）/ `all`（`search=0`）。`search_sinta_journal(keyword, 1 if mode=="title" else 0, ...)`（L344-349） |
| `-a` / `--affil` | 任意 | 取得結果の `affiliation` 文字列に対する後段フィルタ（L130-131）。検索リクエスト自体には渡らない |
| `-f` / `--format` | 既定 `json` | `json` または `csv` |
| `--fetch-mode` | 既定 `basic` | `basic`（検索結果のみ）/ `detail`（各候補のプロフィールページも取得） |

引数なしで実行すると `parser.print_help(stderr)` の上 `exit(1)`（L339-341）。`-q` 未指定など argparse エラーは exit code 2（argparse既定）。

### 1.2 title 検索 / ISSN 検索の可否

- `-q` は **キーワード文字列のみ**。SINTA検索ページ `https://sinta.kemdiktisaintek.go.id/journals?q=<keyword>&search=<0|1>` への GET（L37-38, L304）。
- **ISSN を検索キーとして渡す手段はない**。CLI に ISSN 専用オプションは存在しない。
- ISSN は **出力側**でのみ得られる。`BASIC_FIELDS`（L47-53: `journal_name, sinta_level, affiliation, journal_id, profile_url`）には ISSN が含まれない。`--fetch-mode detail` のときだけ `DETAIL_FIELDS`（L55-68）に `p_issn` / `e_issn` が追加される。

### 1.3 出力形式（JSON）

- `-f json`（既定）: 結果が1件以上のとき `json.dumps(results, indent=4, ensure_ascii=False)` を stdout に出力（L354-355）。結果が0件のときは **何も出力せず** `sys.exit(0)`（L351-352）。
- `-f csv`: `csv.DictWriter` で同フィールドを出力（json と排他、本 adapter では未使用）。
- basic mode の1件あたりのフィールド: `journal_name, sinta_level, affiliation, journal_id, profile_url`（`project_record()` L297-299）。
  - `sinta_level`: `format_sinta_level()`（L103-109）で正規化済みの raw 表記（例 `"S1 Accredited"`、不明時 `"N/A"`）。
  - `journal_id` / `profile_url`: `/journals/profile/(\d+)` または `[?&]id=(\d+)` を href から正規表現抽出（L151-158）。見つからない場合は両方 `"N/A"`。
  - `journal_name`: `affil-name` 要素のテキスト。要素自体が無い場合は `"Unknown"`（L126、稀なケース）。
  - `affiliation`: `affil-loc` 要素のテキストのうち `|` 区切り前半（L166）。要素が無ければ空文字。
- detail mode の追加フィールド: `p_issn, e_issn, subject_area, website_url, editor_url, garuda_url, google_scholar_url`。`p_issn`/`e_issn` も値が無ければ `"N/A"`（L212-217）。

### 1.4 timeout / error / not_found / multiple の扱い

- CLI 自体に**全体タイムアウトはない**。各 HTTP GET に `timeout=25`（requests側、L86）、`retries=3`、検索時 `1.5–3.5s`・detail時 `3.0–6.0s` のランダム待機（L71-77）、403/429時は `10–30s × (attempt+1)` の追加待機（L87-88）。`detail` mode では候補数 × プロフィール取得が直列実行されるため、候補が多いと総実行時間が大きく伸びる。
- **検索リクエスト失敗**（3回リトライ後も失敗）: `fetch_html` が `None` を返し、`search_sinta_journal` が `"Error: failed to retrieve SINTA search results"` を stderr に出力して `[]` を返す（L305-307）。`main()` は `if not results: sys.exit(0)` のため **exit code 0・stdout空・stderr非空**になる。
- **0件検索**（検索自体は成功、`list-item` が0件）: exit code 0・stdout空・**stderr空**。
  - → 上記「検索失敗」と「0件」は **exit codeとstdoutだけでは区別できない**。stderr の有無で区別する必要がある（§2 の判定方針参照）。
- **1件**: exit 0、stdout は1要素のJSON配列。
- **複数件**: exit 0、stdout はN要素のJSON配列。`-a/--affil` 指定時はaffiliation文字列に部分一致しない候補が事前に除外される（L130-131、本 adapter では未使用）。
- detail mode で個別候補のプロフィール取得が失敗した場合、その候補の `detail_fetched`/`parse_status` 等の内部フィールドに記録されるが、これらは `DETAIL_FIELDS` に含まれず**最終出力には現れない**（L297-299, L55-68）。CLI全体としてはエラーにならない。

---

## 2. 呼び出し方式の設計方針（参考）

adapter の呼び出し方式は、次の方針を前提に設計する。

- **adapter command は既定値なし・明示必須**。スクリプトパスのみを受け取り、実行インタプリタは別引数（既定 `sys.executable`）とする。インタプリタ込みのコマンド文字列は渡さない。
- **subprocess 呼び出し**は `subprocess.run(cmd, check=False, text=True, capture_output=True, timeout=...)`（timeout 既定 180 秒）で行う。
- **JSON parse は防御的に行う**。空文字は 0 件として扱い、`json.loads` 失敗時はログ混入対策として最初の `[`/`{` から最後の `]`/`}` までを再切り出して再 parse する。SINTA CLI の `-f json` 出力は常に「フラットな `list[dict]`」または「空文字（0件）」である。
- **「検索失敗」と「0件」の区別**は exit code と stdout だけではできない（§1.4）。`returncode == 0` かつ stdout 空 かつ stderr 非空 の場合を検索失敗（`adapter_error`）として扱う。
- **1行のエラーで全体を止めない**。fetch-journal 側は adapter 呼び出しを行単位で例外捕捉し、エラー行を記録して次の行へ継続する。
- **grade の正規化は取得時には行わない**。adapter はソース表記の raw 値をそのまま返す（adapter contract §3）。

---

## 3. 実装場所

- `adapters/sinta.py`（新規）。既存の `adapters/mock.py` / `adapters/sealib.py` と同じディレクトリ・同じ `fetch_journal(...)` エントリポイント形式。
- `adapters/__init__.py` の変更は不要（既存パッケージにファイルを追加するのみ）。

---

## 4. `fetch_journal` 関数仕様案

```python
def fetch_journal(
    query: str,
    source: str = "SINTA",
    command: str | None = None,
    python: str | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    ...
```

| 引数 | 役割 | 既定値・必須性 |
| --- | --- | --- |
| `query` | SINTA検索キーワード（`-q` にそのまま渡す） | 必須 |
| `source` | candidate/envelope の `source` 値 | 既定 `"SINTA"`（mock/sealib adapterと同じパターン） |
| `command` | `sinta-full-cli-v3.py` のスクリプトパス | **既定値なし・必須**。`None`/空文字なら `adapter_error`（§8） |
| `python` | 実行インタプリタ | `None` なら `sys.executable`。SINTA CLI は `requests`/`beautifulsoup4` に依存するため、journal-metrics-tools の venv とは別の venv（例: `../sinta-full-cli-v3/.venv/bin/python`）を指す運用を想定 |
| `timeout` | `subprocess.run` の `timeout`（秒） | 既定 `180` |

### 4.1 内部コマンド構成（固定値）

```python
cmd = [
    python or sys.executable,
    command,
    "-q", query,
    "-m", "title",
    "-f", "json",
    "--fetch-mode", "basic",
]
```

- `-m title`: `main.search_query`/`main.journal_name`（journal タイトル文字列）と意味的に対応する「タイトル検索」を既定とする。
- `--fetch-mode basic`: プロフィールページへの追加アクセスを行わず、応答時間とSINTAサイトへの負荷を抑える。標準検索結果では `issn`/`eissn` が得られないことがある（§6）。
- `mode` / `fetch_mode` を呼び出し引数として公開するかは将来の検討事項（§9 非対象）。
- `command` は **単一のスクリプトパス文字列**として扱い、`shlex.split` 等によるマルチトークン解釈は行わない（§9 非対象）。

### 4.2 戻り値

`docs/adapter-contract.md` §4.3 の envelope 形式（`status` / `source` / `query` / `candidates` / `error`）。

---

## 5. query の扱い

- `adapters/sinta.py` の `fetch_journal()` は **文字列 `query` のみ**を受け取り、`main` シートの列構成を意識しない。
- どの列から `query` を作るかは `journal_metrics.py` の `query_for_adapter()` が既に決めている:
  ```python
  if adapter == "sealib":
      query_headers = ["name", "o_name"]
  else:
      query_headers = ["search_query", "journal_name"]
  ```
  `adapter != "sealib"` の場合（mock・sinta を含む）、`search_query` を優先し、空なら `journal_name` にフォールバックする。**`main.name` へのフォールバックはない**。SINTA adapter 用に `query_for_adapter()` を変更する必要は **ない**。
- `search_query` も `journal_name` も空の場合、`query_for_adapter()` は `""` を返す。現行 `fetch_journal_command` は non-sealib adapter に対して:
  ```python
  query = query_for_adapter(row, main_headers, args.adapter)
  if not query:
      if args.adapter == "sealib":
          main_ws.cell(..., value="adapter_error")
      continue
  ```
  → **空 query の行は adapter を呼ばずに silent skip**（`main.status` は変更されない）。`sealib` のみ `adapter_error` を明示設定する非対称な挙動になっている。
- **将来の論点（本書では決定しない）**: `docs/grade-and-source-policy.md` §2.1 の通り SINTA は metrics source（grade必須・export TSV 出力対象）であるため、`search_query`/`journal_name` が両方空の行を sealib と同様に `main.status="adapter_error"` として可視化すべきか、mock と同じ silent skip のままでよいかは、将来の接続設計で判断する。
- 防御的実装として、`adapters/sinta.py` の `fetch_journal("")`（空文字を渡された場合）は `adapters/sealib.py` と同様に **`not_found`**（候補なし、`error=null`）を返す方針とする。`journal_metrics.py` から空文字で呼ばれることは上記の通り想定されないが、adapter単体としての防御である。

---

## 6. adapter contract candidate へのマッピング

SINTA CLI（`--fetch-mode basic`, `-f json`）の1件の dict を、`docs/adapter-contract.md` §4.1 の candidate フィールドへ次の通りマッピングする。

| candidate フィールド | SINTA CLI 出力フィールド | マッピング方針 |
| --- | --- | --- |
| `source` | （固定値） | `"SINTA"`（`fetch_journal` の `source` 引数値） |
| `external_journal_id` | `journal_id` | 文字列のまま。`"N/A"` → `null` |
| `title` | `journal_name` | そのまま（候補が存在する限り必須）。SINTA側が `"Unknown"` を返した場合もそのまま通す（raw値方針） |
| `issn` | `p_issn`（basic modeでは出力されないことがある） | 必要時のみ detail mode で補完（§0） |
| `eissn` | `e_issn`（basic modeでは出力されないことがある） | 必要時のみ detail mode で補完（§0） |
| `publisher` | `affiliation` | 空文字 → `null`、それ以外はそのまま |
| `country` | （固定値） | `"ID"`（SINTAはインドネシア限定ソース。`docs/adapter-contract.md` §5.1/§5.2 のSINTA例と一致） |
| `grade` | `sinta_level` | raw値のまま（例 `"S1 Accredited"`）。`"N/A"` → `null`。正規化なし（§7） |
| `url` | `profile_url` | `"N/A"` → `null`、それ以外はそのまま |
| `note` | （なし） | 最小実装では `null`。raw情報は `journal.raw_json`（`journal_mapper._row_from_candidate` が candidate全体 + `query` を保存）から参照可能 |

`"N/A"` → `null` の変換は SINTA CLI が「値なし」を表す内部規約（L181-191等）であり、adapter contract の「不明時は `null`」（§4.1）に合わせるための adapter 側の変換である。

---

## 7. grade 方針

- `adapters/sinta.py` は `sinta_level`（例 `"S1 Accredited"` 〜 `"S6 Accredited"`、または SINTA表示に依存するその他raw文字列、`"N/A"`時は`null`）を **そのまま** `grade` として返す。
- 正規化は adapter に持ち込まない。`docs/adapter-contract.md` §3「grade はソース表記の raw 値のまま返し、adapter は正規化を行わない」に合致。
- export TSV の `grade` 列に raw値（`"S1 Accredited"`等）をそのまま使うか、`fetch-journal`/`convert` 側で正規化を挟むかは、`docs/grade-and-source-policy.md` §7 で「grade値の正規化」を非対象としており、本書でも結論を出さない。**将来判断する**。

---

## 8. status 変換

`docs/adapter-contract.md` §4.4 の語彙（`fetched` / `not_found` / `multiple_candidates` / `adapter_error`）に対し、SINTA CLI の実行結果から以下のように決定する。

| SINTA CLI 実行結果 | candidates件数 | `envelope.status` | `error` |
| --- | --- | --- | --- |
| `command` が `None`/空文字 | - | `adapter_error` | `"command is required"` |
| `python`/`command` が存在しない（`FileNotFoundError`） | - | `adapter_error` | 例外メッセージ |
| `subprocess.run` が `TimeoutExpired` | - | `adapter_error` | `"timeout after {timeout}s"` 等 |
| `returncode != 0` | - | `adapter_error` | stderr（空なら stdout） |
| `returncode == 0`, stdout空, stderr非空 | - | `adapter_error` | stderr（§1.4「検索失敗」） |
| `returncode == 0`, stdout空, stderr空 | 0 | `not_found` | `null` |
| stdout が JSON として parse できない | - | `adapter_error` | parse例外メッセージ |
| stdout が1要素のJSON配列 | 1 | `fetched` | `null` |
| stdout が2要素以上のJSON配列 | 2+ | `multiple_candidates` | `null` |

`journal.fetch_status` への対応（`docs/adapter-contract.md` §4.4 / `journal_mapper.FETCH_STATUS_BY_ENVELOPE_STATUS`）は既存どおり: `fetched→ok`, `not_found→none`, `multiple_candidates→multiple`, `adapter_error→error`。SINTA向けの変更は不要。

---

## 9. 実装範囲（最小実装）

**含む**:

1. `adapters/sinta.py` を新規作成し、`fetch_journal(query, source="SINTA", command=None, python=None, timeout=180) -> dict` を実装する。
2. `command` が `None`/空文字の場合は `adapter_error` envelope を返す（§8）。
3. §4.1 のコマンド構成で `subprocess.run(cmd, check=False, text=True, capture_output=True, timeout=timeout)` を実行する。
4. §8 の表に従い、CLI失敗・timeout・JSON parse失敗を `adapter_error` envelope に変換する。
5. stdout を `json.loads`（必要なら §2 の防御的 parse も検討）してリスト化し、§6 のマッピングで candidate を構築する。
6. candidate数から `fetched`/`multiple_candidates`/`not_found` を決定し envelope を返す（§8）。
7. 単体テスト: 実ネットワークに依存しない、固定 stdout/stderr/returncode を返すスタブスクリプト（または `subprocess.run` のモック）で 0/1/2件・エラー・timeoutの各分岐を検証する（`adapters/mock.py` のテストパターンに準拠）。

**含まない（将来 or 別タスク）**:

- `journal_metrics.py` の `--adapter` choices への `"sinta"` 追加、CLI引数（`--sinta-command` 等）の追加、`fetch_journal_command` への分岐追加。
- `query_for_adapter()` の変更（§5の通り変更不要）。
- 空 `search_query`/`journal_name` 時の `main.status` 扱い（§5の論点）。
- grade 正規化。
- `mode`/`fetch_mode`/`affil` の adapter引数化。
- 将来 source adapter。
- `convert` / 後段 DB 関連の変更。
- SINTA への本番アクセス・大量取得。

---

## 10. 非対象（本書全体）

- SINTAサイトへの本番アクセス・大量取得。
- 将来 source adapter。
- grade正規化。
- 後段 import ツールの変更。
- SEALIB DBへの書き込み。
- 本番データの投入。
- `journal_metrics.py` / `journal_mapper.py` / `adapters/mock.py` / `adapters/sealib.py` / `README.md` の変更。

---

## 関連ドキュメント

- `docs/adapter-contract.md`（候補・envelope・status語彙の共通契約、convert シートと TSV 出力の要点）
- `docs/grade-and-source-policy.md`（`metric_source` 役割分類、SINTAをmetrics sourceとして扱う前提）
- `journal_metrics.py`（`query_for_adapter`, `fetch_journal_command`, `MAIN_STATUS_BY_ENVELOPE_STATUS`）
- `journal_mapper.py`（`map_envelope_to_journal_rows`, `raw_json` への candidate+query保存）
- `adapters/sealib.py`（既存adapterの実装パターン・`db_path is None`→`adapter_error`の前例）
- `../sinta-full-cli-v3/sinta-full-cli-v3.py`, `../sinta-full-cli-v3/README.md`（SINTA CLI仕様）
