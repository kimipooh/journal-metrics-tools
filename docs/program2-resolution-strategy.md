# Program 2 投入方式 設計判断（Phase 3F）

**作成日**: 2026-06-14 | **ステータス**: 設計判断確定（未実装・コード変更なし）
**親文書**: `docs/sealib-api-oai-compatibility-audit.md`（Phase 3E）
**対象**: journal-metrics-tools の `convert` / `enrich-db` および SEALIB側 Program2（`journal_metrics` 投入）の方式決定

> 本書は **設計判断のみ**を確定する。`convert` / `enrich-db` / Program2 の実装、DB書き込み、header更新、本番データ投入のいずれも行わない。

---

## 0. 決定事項（要約）

**Program2 投入方式は (B) 名前再解決方式を採用する。**

(A) 直結方式（`convert.id`→`ref_id`、`convert.journal_name`→`ref_name`を無条件にそのまま投入する方式）は **採用しない**。

---

## 1. 背景

Phase 3E（`docs/sealib-api-oai-compatibility-audit.md` §5.2）で、`journal_metrics` 投入方式には2系統が存在することが判明した。

| | (A) 直結方式 | (B) 名前再解決方式 |
|---|---|---|
| 現状 | `03-1-import-metrics-sinta.php`（SINTA専用・実装済み） | `journal-metrics-semi-auto-design.md` §6 が計画する `03-2-import-metrics.php`（未実装） |
| `ref_id` | TSVの`id`をそのまま投入 | TSVの`sealib_name`/`sealib_o_name`で`header`を完全一致検索し、解決後の`header.id`を投入 |
| `ref_name` | TSVの`name`（≈SEALIB側名）をそのまま投入 | Program2が解決後の`header.name`を自分でセット（TSVからは受け取らない） |
| `header.id`変動への耐性 | なし（フルビルドで`ref_id`が孤立しうる） | あり（投入時点の`header`に対して毎回再解決） |

rebuild-plan.md §8 の現行マッピング（`id`→`ref_id`、`journal_name`→`ref_name`）は (A) に近い構成だった。本書で (B) を正式採用方針として確定し、Phase 4A以降の `CONVERT_HEADERS` 再設計の前提とする。

---

## 2. 採用方式: (B) 名前再解決方式

### 2.1 全体フロー

```
journal-metrics-tools（本リポジトリ）
  main:    id(補助), name, o_name, issn, eissn, journal_name, note, status
  journal: 確定candidate（journal_type, grade, profile_url, external_journal_id, affiliation, raw_json, ...）
       │
       ▼ convert（Phase 4A/4B）
  convert: sealib_name, sealib_o_name, sealib_id(補助), metric_source, metric_country, grade, url, note, convert_status
       │
       ▼ TSV export（Phase 4C）
  TSV: sealib_name, sealib_o_name, sealib_id, metric_source, metric_country, grade, url, note
       │  ※ ref_id / ref_name は含めない
       ▼ Program2（03-2-import-metrics.php・SEALIB側・Phase 5）
  1. sealib_name / sealib_o_name で header を完全一致検索
       - 1件 → 採用
       - 複数件（同名） → sealib_id が候補に含まれればそれを採用。無ければ ambiguous = スキップ＋ログ
       - 0件 → sealib_id で直接照合（WHERE id=:sealib_id）。
                見つかれば名前不一致を warning として記録し採用、
                見つからなければ unmatched = スキップ＋ログ
  2. ref_id   = 解決後 header.id
  3. ref_name = 解決後 header.name
  4. metric_source 単位で DELETE → INSERT（ref_id, ref_name, metric_source,
     metric_country, grade, url, note, imported_at）
```

### 2.2 各ステップの責務

| 工程 | 責務 | 担当フェーズ |
|---|---|---|
| convert | Program2の照合キー（`sealib_name`/`sealib_o_name`/`sealib_id`）と指標ペイロード（`metric_source`/`metric_country`/`grade`/`url`/`note`）をTSVへ出力 | Phase 4A/4B（journal-metrics-tools） |
| Program2 | TSVの照合キーで投入時点の`header`を再解決し、`ref_id`/`ref_name`を**自分で**算出してINSERT | Phase 5（sealib側、別タスク） |

`ref_id`/`ref_name`は **convertの出力にも、TSVにも含めない**。これらはProgram2が投入時点の`header`から都度導出する値であり、journal-metrics-tools側が保持・運搬する情報ではない。

---

## 3. (A) 直結方式を採用しない理由

1. **`convert.id`→`ref_id`直結**: `convert.id`（≈`main.id`、enrich-dbで補完される`header.id`のスナップショット）は、journal-metrics-tools側での取得時点の値である。SEALIBの`all_data_import.sh`によるフルビルドで`header.id`が変わった場合、投入される`ref_id`は**もう存在しないID**を指すことになる。
2. **`convert.journal_name`→`ref_name`直結**: `journal_name`はjournalシートの確定candidateの名称、すなわち**外部ソース（SINTA等）側の表記**である。これを`ref_name`にそのまま入れると、`ref_name`が「SEALIB側の現在の`header.name`」を表すという(B)方式の意味（Program2が自ら設定する値）と矛盾する。
3. **サイレント欠落のリスク**: `ref_id`が孤立しても、REST API `?include=metrics`は**エラーを返さず**`metrics: []`を返す（Phase 3E §2.4）。`ENABLE_METRICS=0`時の黒子無視と同様、運用上**気づきにくい**形で指標が表示されなくなる。
4. (A)はSINTA専用ハードコード（`metric_source='SINTA'`, `metric_country='ID'`）の延長であり、複数ソース対応の汎用ツールという journal-metrics-tools の目的（`docs/rebuild-plan.md` §1）に合わない。

---

## 4. convert シート / CONVERT_HEADERS への影響整理

### 4.1 基本候補列（本フェーズで整理。最終確定はPhase 4A）

```
sealib_name  sealib_o_name  sealib_id  metric_source  metric_country  grade  url  note
```

### 4.2 現行 CONVERT_HEADERS との対比

現行（`journal_metrics.py`）:
```
id, journal_type, grade, external_journal_id, profile_url, journal_name, affiliation, note, convert_status
```

| 現行列 | (B)方式での扱い | 備考 |
|---|---|---|
| `id` | `sealib_id`へ転換（**補助**: disambiguation / 0件時fallback / 名前不一致warning用） | `ref_id`への直結はしない（§3） |
| `journal_type` | `metric_source`相当 | 列名を`metric_source`に統一するかは Phase 4A で確定（`journal_metrics`列名と1:1対応させる案） |
| `grade` | 維持 | そのまま`journal_metrics.grade`へ |
| `profile_url` | `url`相当 | 列名統一はPhase 4Aで確定 |
| `journal_name` | **`ref_name`には使わない**。保持して候補名トレーサビリティとして残すか、`note`集約へ回すかをPhase 4Aで決定 | (B)では`ref_name`はProgram2が算出するため不要 |
| `external_journal_id` | `note`集約候補（§6） | `journal_metrics`に対応列なし |
| `affiliation` | `note`集約候補（§6） | 同上 |
| `note` | 維持（集約方針は§6） | |
| `convert_status` | 維持 | ワークフロー状態列として不変 |
| （新規） | `sealib_name` | `main.name`から。**必須**（Program2の主照合キー） |
| （新規） | `sealib_o_name` | `main.o_name`から。**任意・fallback照合用** |
| （新規） | `metric_country` | §5参照。**必須** |

### 4.3 main → convert の参照元

`MAIN_HEADERS`の`id`/`name`/`o_name`がconvertの`sealib_id`/`sealib_name`/`sealib_o_name`の供給元となる（enrich-dbで補完される値、§7参照）。

---

## 5. `metric_country` の扱い

- `journal_metrics.metric_country`は REST API `?include=metrics`で**`country`として公開**される（Phase 3E §2.3）。
- `metric_country`は**指標ソース側の国コード系**（例: SINTAは`ID`=Indonesia, ISO的表記）であり、SEALIB `header.country`（**LCコード**、Indonesia=`IO`）とは**異なる符号系**である。
- したがって **`header.country`を変換なしにそのまま`metric_country`へコピーしてはならない**。
- 値の出どころは指標ソース（adapter）側が持つ国コード表記である。`docs/adapter-contract.md`のcandidate `country`フィールド（現状`raw_json`にのみ保持）を、convert/journalシートへどう昇格させるか、または`journal_type`別の固定値injection（旧`03-1`の`'ID'`ハードコード相当の一般化）にするかをPhase 4Aで確定する。
- `adapters/sealib.py`の`--country`フィルタ（`header.country`=LCコード前提）と、convert側`metric_country`（指標ソース側コード）は**名前が似ているが別概念**である点をPhase 4Aのドキュメントで明示する。

---

## 6. `note` 集約方針（仮決め）

`journal_metrics.note`はREST APIで**唯一公開される自由記述フィールド**（`format_metric()`の`note`）。以下を集約候補とする。

- `external_journal_id`（`journal_metrics`に対応列なし）
- `affiliation` / `publisher`
- `eissn`（`header`/`journal_metrics`いずれにも対応列なし）
- その他 adapter固有情報（`raw_json`内の項目から必要に応じて）

**方針（仮）**:
- `note`はREST APIで公開されるため、**書式を固定**し、機械的にパース可能な形にする（例: `key=value; key=value`形式）。
- `raw_json`の生ダンプや、過度に内部的な情報（デバッグ用フィールド等）は入れない。
- 最終的なキー集合・区切り文字・エンコーディングはPhase 4A/4Bで確定する。本書では「集約候補と公開上の制約」のみを明文化する。

---

## 7. enrich-db との関係

- `enrich-db`（旧Phase 4、`docs/rebuild-plan.md` §6）は、`main.id`/`name`/`o_name`をSEALIB DBから補完する**補助工程**である。
- (B)方式では、`enrich-db`が補完した`sealib_name`/`sealib_o_name`/`sealib_id`は**convertへの入力（照合キーの種）**として使われるが、**最終的な`ref_id`/`ref_name`の確定はProgram2が投入時点のSEALIB DBに対して行う**。
- すなわち、`enrich-db`実行時点と`Program2`実行時点の間で`header.id`が変わっていても、(B)方式は名前一致で再解決するため**整合性が保たれる**（§3で述べた(A)方式の脆弱性を回避）。
- **enrich-dbの結果は補助情報であり、最終的な参照整合性の保証はenrich-dbではなくProgram2が担う**。この役割分担をPhase 4A以降のドキュメントでも維持する。

---

## 8. REST API / OAI-PMH への影響整理

Phase 3E（`docs/sealib-api-oai-compatibility-audit.md`）の確認結果を踏襲。(B)方式の採用は以下と矛盾しない。

- **REST API v1**: `ref_id`/`ref_name`は`format_metric()`で公開されない（非公開フィールド）。公開されるのは`source`(←`metric_source`) / `country`(←`metric_country`) / `grade` / `url` / `note` / `imported_at`の6項目のみ。(B)方式が`ref_id`/`ref_name`をどう解決しても、**API公開フィールドの構成・公開仕様自体には影響しない**。
- **`metric_source`絞り込み**: `header.id IN (SELECT ref_id FROM journal_metrics WHERE metric_source IN (...))`。(B)方式で`ref_id`が常に現行`header.id`を指すことが保証されるため、この絞り込みの正確性が(A)方式より向上する（孤立`ref_id`が無くなる）。
- **OAI-PMH 2.0**: `journal_metrics`を一切参照しない（Phase 3E §3.1で確認済み）。journal_metrics投入方式の変更（(A)→(B)）はOAI-PMH出力に**一切影響しない**。`header`を更新しない限りOAI-PMHへの影響は生じない。

---

## 9. 非対象（本フェーズで行わないこと）

- Program2（`03-2-import-metrics.php`）の実装
- `convert`コマンドの実装
- `enrich-db`コマンドの実装
- SEALIB DBへの書き込み
- `header`メタ情報の更新
- 本番データの投入

---

## 10. 次フェーズ提案

| Phase | 内容 | 主な成果物 |
|---|---|---|
| **4A** | `convert`シート / `CONVERT_HEADERS`再設計 | §4の対比表に基づき列構成を確定（`sealib_name`/`sealib_o_name`/`sealib_id`/`metric_source`/`metric_country`/`grade`/`url`/`note`、列名統一・`journal_name`の扱い・`note`集約フォーマット） |
| **4B** | `convert`生成ロジック実装 | main↔journal確定行からconvert行を生成（`convert_status`でゲート） |
| **4C** | Program2向けTSV export実装 | `convert`→TSV（(B)方式の入力列: `sealib_name`/`sealib_o_name`/`sealib_id`/`metric_source`/`metric_country`/`grade`/`url`/`note`） |
| **5** | SEALIB側 Program2（`03-2-import-metrics.php`）実装/調整 | sealib repoでの別タスク。§2.1の再解決フロー（名前完全一致→`sealib_id`補助→ambiguous/unmatchedログ）を実装 |

各Phaseは「最小実装→レビュー」のサイクルを維持し、Claude（設計・整理）→Codex（実装）の役割分担を踏襲する。

---

## 関連ドキュメント

- `docs/sealib-api-oai-compatibility-audit.md`（Phase 3E。本書の前提調査）
- `docs/rebuild-plan.md` §6-8（enrich-db / convert / journal_metricsマッピングの旧案）
- `docs/adapter-contract.md`（candidate `country`フィールドの扱い）
- sealib `docs/journal-metrics-semi-auto-design.md` §6（Program2再解決フローの原典）
- sealib `docs/sealib-journal-metrics-tools-design.md`
