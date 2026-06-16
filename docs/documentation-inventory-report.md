# Documentation Inventory Report

> 本書は Phase 9C 調査結果のみ。コード変更・ファイル移動・削除は行わない。

作成日: 2026-06-16

---

## 1. ドキュメント一覧

### ルート

| ファイル | 行数 | 概要 |
|---|---|---|
| `README.md` | 295 | 英語版 README（利用者向け） |
| `README-ja.md` | 296 | 日本語版 README（利用者向け） |
| `LICENSE` | 21 | MIT License |

### docs/

| ファイル | 行数 | 概要 |
|---|---|---|
| `docs/workflow.md` | 283 | ステップ別運用手順（英語） |
| `docs/workflow-ja.md` | 291 | ステップ別運用手順（日本語） |
| `docs/adapter-contract.md` | 218 | adapter 共通インタフェース仕様 |
| `docs/sinta-adapter-design.md` | 301 | SINTA adapter 実装設計 |
| `docs/rebuild-plan.md` | 280 | 全体再構築計画・Phase 進行記録 |
| `docs/convert-sheet-redesign.md` | 256 | convert シート / CONVERT_HEADERS 再設計（Phase 4A） |
| `docs/grade-and-source-policy.md` | 162 | grade / metric_source 投入ポリシー（Phase 6B） |
| `docs/validation-layering.md` | 121 | validate-tsv の責務分担設計（Phase 5A-2） |
| `docs/program2-dry-run-design.md` | 249 | Program2 dry-run 仕様設計（Phase 5A） |
| `docs/program2-resolution-strategy.md` | 193 | Program2 投入方式 設計判断（Phase 3F） |
| `docs/sealib-api-oai-compatibility-audit.md` | 239 | SEALIB REST API / OAI-PMH 整合性調査（Phase 3E） |

### .codex/tasks/ （Codex 実装引き継ぎタスク、17件）

| ファイル | 概要 |
|---|---|
| `phase1-journal-metrics-template.md` | テンプレート実装 |
| `phase2a-adapter-contract.md` | adapter contract 策定 |
| `phase2b-mock-adapter.md` | mock adapter 実装 |
| `phase2c-journal-mapper.md` | journal mapper 実装 |
| `phase2d-fetch-journal-mock-cli.md` | fetch-journal (mock) CLI 実装 |
| `phase3a-sealib-adapter-design.md` | SEALIB adapter 設計 |
| `phase3c-fetch-journal-sealib-cli.md` | fetch-journal (sealib) 実装 |
| `phase3d-sealib-real-db-readonly-verification.md` | SEALIB DB read-only 検証 |
| `phase3f-program2-resolution-strategy.md` | Program2 方式判断 |
| `phase4a-convert-sheet-redesign.md` | convert シート再設計 |
| `phase5a-2-validation-layering.md` | 二段階検証責務分担 |
| `phase5a-program2-dry-run-design.md` | Program2 dry-run 設計 |
| `phase5b-program2-dry-run-implementation.md` | Program2 dry-run 実装 |
| `phase5c-program2-production-import-design.md` | Program2 本番投入設計 |
| `phase6b-grade-and-source-policy.md` | grade / source ポリシー |
| `phase7a-sinta-adapter-design.md` | SINTA adapter 設計 |
| `phase7k0-fetch-journal-sealib-status-fix.md` | SEALIB status fix |

---

## 2. 分類結果

### A. User Documentation（利用者向け）

公開 README に含める対象。

| ファイル | 状態 | 備考 |
|---|---|---|
| `README.md` | 公開済み | Phase 9A-2〜5b で整備完了 |
| `README-ja.md` | 公開済み | 同上 |
| `docs/workflow.md` | 公開済み | ステップ別詳細手順（英語） |
| `docs/workflow-ja.md` | 公開済み | ステップ別詳細手順（日本語） |

### B. Developer Documentation（開発者向け）

adapter 実装者・コード貢献者向け。

| ファイル | 状態 | 備考 |
|---|---|---|
| `docs/adapter-contract.md` | 現役 | adapter インタフェース仕様。新 adapter 実装時の参照先 |
| `docs/sinta-adapter-design.md` | 現役 | SINTA adapter の実装詳細。sinta-full-cli-v3 連携仕様 |

### C. Internal Design Notes（内部設計記録）

実装時の意思決定記録。直接参照は減っているが、設計背景の確認に使用。

| ファイル | 状態 | 備考 |
|---|---|---|
| `docs/rebuild-plan.md` | アーカイブ候補 | 全 Phase 計画の記録。Phase 7K 相当まで完了。歴史的参照として保持 |
| `docs/convert-sheet-redesign.md` | アーカイブ候補 | Phase 4A 完了済み。CONVERT_HEADERS の設計根拠として参照可能 |
| `docs/grade-and-source-policy.md` | 現役（参照用） | grade / metric_source の分類ポリシー。convert コマンドの動作根拠 |
| `docs/validation-layering.md` | 現役（参照用） | validate-tsv の責務範囲の定義。TSV 検証レイヤーの設計根拠 |

### D. Archive / Candidate for Archive（アーカイブ候補）

役割が終了、または本ツールの責務範囲外となった文書。

| ファイル | 理由 |
|---|---|
| `docs/program2-dry-run-design.md` | Program2 は本ツールのスコープ外（Phase 9A-2 で確定） |
| `docs/program2-resolution-strategy.md` | 同上 |
| `docs/sealib-api-oai-compatibility-audit.md` | Phase 3E 完了。SEALIB API 連携は採用せず（SQLite read-only に確定）。一回限りの調査記録 |
| `.codex/tasks/` (17件) | Codex への実装引き継ぎ用タスク。全 Phase 完了済み。ツール内部運用記録 |

---

## 3. 公開対象・内部対象の判定

| 区分 | ファイル群 | GitHub 公開 |
|---|---|---|
| 公開 | README.md, README-ja.md, docs/workflow.md, docs/workflow-ja.md, LICENSE | ✅ 公開 |
| 開発者向け公開 | docs/adapter-contract.md, docs/sinta-adapter-design.md | ✅ 公開（開発者参照用） |
| 内部参照 | docs/rebuild-plan.md, docs/convert-sheet-redesign.md, docs/grade-and-source-policy.md, docs/validation-layering.md | 🔶 公開しても支障なし（内部設計記録） |
| アーカイブ推奨 | docs/program2-*.md, docs/sealib-api-oai-compatibility-audit.md | 🔶 公開しても支障なし。docs/archive/ 移動を推奨 |
| 内部運用のみ | .codex/tasks/ (17件) | ✅ .gitignore 済み（非公開） |

---

## 4. 推奨ディレクトリ構成

現状からの移動は行わない。将来の整理への提案のみ。

```
journal-metrics-tools/
├── README.md                        # A: User
├── README-ja.md                     # A: User
├── LICENSE
│
└── docs/
    ├── workflow.md                  # A: User
    ├── workflow-ja.md               # A: User
    │
    ├── developer/                   # B: Developer（新設推奨）
    │   ├── adapter-contract.md
    │   └── sinta-adapter-design.md
    │
    ├── design/                      # C: Internal Design（新設推奨）
    │   ├── rebuild-plan.md
    │   ├── convert-sheet-redesign.md
    │   ├── grade-and-source-policy.md
    │   └── validation-layering.md
    │
    └── archive/                     # D: Archive（新設推奨）
        ├── program2-dry-run-design.md
        ├── program2-resolution-strategy.md
        └── sealib-api-oai-compatibility-audit.md
```

**移動する場合の注意点:**

- `docs/adapter-contract.md` は `docs/rebuild-plan.md` §7 から参照されている
- `docs/adapter-contract.md` は `docs/sinta-adapter-design.md` から参照されている
- 移動時はクロスリンクの修正が必要

---

## 5. AGENT.md に入れるべき項目

AGENT.md はコード貢献者・AI エージェント向けのプロジェクト概要として機能させる。

```markdown
## Project Overview
Journal Metrics Tools is a workbook-based CLI tool for collecting, reviewing,
reconciling, and exporting journal-related information from multiple sources.

## Architecture
- Workbook (Excel): main / journal / convert sheets
- adapter → fetch-journal → review → convert → export-tsv → validate-tsv
- Adapter-based: sealib (metadata), sinta (evaluation), mock (testing)

## Adapter Concept
- sealib: metadata enrichment only (main.id / main.issn / main.o_name)
- sinta: journal evaluation information (accreditation rankings)
- mock: fixed responses for testing and workflow validation
- Adapter contract: docs/adapter-contract.md

## Workbook Structure
- main sheet: human-edited journal list (input)
- journal sheet: fetched candidates (written by fetch-journal)
- convert sheet: export-ready rows (written by convert)

## Status Vocabulary
main.status: [blank] / pending / fetched / not_found / multiple_candidates
             / adapter_error / skip / done
journal.fetch_status: ok / none / multiple / error
convert.convert_status: ready / hold / skipped

## Key Files
- journal_metrics.py: CLI entry point (all 5 commands)
- adapters/sealib.py: SEALIB SQLite read-only adapter
- adapters/sinta.py: SINTA external CLI adapter
- journal_mapper.py: envelope → journal rows mapping

## Scope Boundary
- Tool outputs: validated TSV
- Downstream DB import: OUT OF SCOPE
- Program2: OUT OF SCOPE
```

---

## 6. CLAUDE.md に入れるべき項目（プロジェクト固有制約）

CLAUDE.md はプロジェクト固有ルールとして Claude Code に読み込ませる。

```markdown
## 修正制約

- CONVERT_HEADERS / PROGRAM2_TSV_HEADERS を変更しない（既存 workbook 互換性）
- main シートの列定義（MAIN_HEADERS 相当）を変更しない
- journal シートの列定義（JOURNAL_HEADERS）を変更しない
- adapter contract（docs/adapter-contract.md）を壊す変更をしない

## スコープ外

- Program2（SEALIB 側 import スクリプト）は本ツールの責務外
- docs/program2-*.md は参照のみ。設計変更に使用しない
- enrich-db コマンドは未実装（計画のみ）。実装指示がない限り触れない

## adapter 関連

- sealib adapter は書誌情報補完のみ（評価情報取得ではない）
- sinta adapter は評価情報取得のみ（書誌補完ではない）
- 新 adapter を追加する場合は docs/adapter-contract.md のインタフェースに従う

## validate-tsv

- validate-tsv は DB 接続不要の構造検証のみ
- Program2 dry-run は validate-tsv の責務外

## .codex/tasks/

- Codex 実装引き継ぎ用。編集・削除しない
- 新タスク作成時は task-YYYYMMDD-HHMM.md 形式

## ドキュメント整合性

- README / README-ja / workflow / workflow-ja を変更した場合は相互整合性を確認する
- docs/adapter-contract.md を変更した場合は docs/sinta-adapter-design.md との整合を確認する
```

---

## 7. 次フェーズ提案

| フェーズ | 内容 | 優先度 |
|---|---|---|
| Phase 9C-1 | AGENT.md 作成（本レポート §5 を素材に） | 高 |
| Phase 9C-2 | CLAUDE.md（プロジェクト固有）作成（本レポート §6 を素材に） | 高 |
| Phase 9D | docs/ ディレクトリ再構成（developer/ design/ archive/ 新設） | 中 |
| Phase 9E | docs/program2-*.md のアーカイブ移動 | 低 |
| Phase 9F | CHANGELOG.md 作成（リリース管理） | 中 |
