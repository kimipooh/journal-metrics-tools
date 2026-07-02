# AGENT.md — Journal Metrics Tools

Project charter for developers, contributors, and AI agents.
For user-facing documentation see README.md.

---

## 1. Project Overview

**Journal Metrics Tools** is a workbook-based CLI tool for collecting, reviewing,
reconciling, and exporting journal-related information from multiple sources.

The tool manages journal lists in an Excel workbook, fetches bibliographic metadata
and evaluation information through a pluggable adapter system, and exports a validated
TSV file. Downstream import of that TSV is outside this tool's scope.

---

## 2. Core Architecture

```
Excel Workbook
 └─ main sheet   (human-edited journal list — input)
       ↓
  fetch-journal --adapter <name>
 └─ journal sheet (fetched candidates — written by fetch-journal)
       ↓
  convert
 └─ convert sheet (export-ready rows — written by convert)
       ↓
  export-tsv  →  output.tsv
       ↓
  validate-tsv  →  errors = 0  →  [downstream import — out of scope]
```

### Commands

| Command | Role |
|---|---|
| `template` | Create a new workbook with pre-defined sheets |
| `fetch-journal` | Collect metadata or evaluation information via an adapter |
| `convert` | Generate export-ready rows from accepted candidates |
| `export-tsv` | Write `convert_status = ready` rows to a TSV file |
| `validate-tsv` | Validate TSV structure without database access |

### Key Files

| File | Purpose |
|---|---|
| `journal_metrics.py` | CLI entry point; all 5 commands |
| `adapters/sealib.py` | SEALIB SQLite read-only adapter |
| `adapters/sinta.py` | SINTA external CLI adapter |
| `journal_mapper.py` | Maps adapter envelopes to `journal` sheet rows |

---

## 3. Information Model

Adapters serve distinct roles. Do not conflate them.

| Adapter | Role | What it fetches |
|---|---|---|
| `sealib` | **Metadata enrichment** | `main.id`, `main.issn`, `main.o_name` from SEALIB SQLite DB |
| `sinta` | **Evaluation information** | SINTA accreditation rankings via `sinta-full-cli-v3` (external CLI) |
| `mock` | **Testing / validation** | Fixed responses; no external tools required |

**SEALIB is not an evaluation source.** It provides bibliographic and holding
information on Southeast Asian periodicals. Its adapter supplements identifier
fields only, and its `journal` rows are always `skipped` by `convert` (never
exported to TSV).

---

## 4. Status Vocabulary

### `main.status`

| Value | Meaning |
|---|---|
| _(blank)_ / `pending` | Not yet fetched |
| `fetched` | Exactly one candidate confirmed |
| `not_found` | No candidates returned |
| `multiple_candidates` | Multiple candidates; disambiguation failed |
| `adapter_error` | Adapter call failed (timeout, path error, etc.) |
| `skip` | Excluded from all fetch operations permanently |
| `done` | Marked complete; excluded from `--update` |

### `journal.fetch_status`

`ok` / `none` / `multiple` / `error`

### `convert.convert_status`

| Value | Exported to TSV |
|---|---|
| `ready` | Yes |
| `hold` | No (evaluation field missing) |
| `skipped` | No (SEALIB / MOCK rows) |

---

## 5. Adapter Contract

All adapters implement the same envelope interface defined in
`docs/adapter-contract.md`. The envelope shape:

```json
{
  "status": "fetched | not_found | multiple_candidates | adapter_error",
  "source": "<adapter identifier>",
  "query": "<search string used>",
  "candidates": [ { ...candidate fields... } ],
  "error": "<message or null>"
}
```

Each candidate maps to one `journal` sheet row. Adapters do not perform Excel I/O.
`fetch-journal` assigns `main_row_id` and writes rows.

---

## 6. Design Principles

- **Adapter-first**: all external data access is isolated in adapters; `journal_metrics.py` is source-agnostic
- **Workbook-centric**: the Excel workbook is the managed data store; no database required for the tool itself
- **Explicit review before export**: candidates are written to `journal` sheet and require human (or scripted) confirmation before `convert` promotes them
- **Separation of collection and import**: the tool's responsibility ends at a validated TSV; import into any downstream system is outside scope
- **Idempotent regeneration**: `convert` deletes all rows then regenerates from scratch on each run — no stale row accumulation

---

## 7. Non-Goals

The following are **outside the scope** of this repository:

- Database import (any system)
- SEALIB-side database import processing (PHP import scripts)
- Writing to the SEALIB database
- REST API or web interface
- Automated scheduling or batch orchestration

The tool outputs a validated TSV and stops there.

---

## 8. Extensibility

The adapter architecture is intentionally extensible. New adapters for additional
metadata or evaluation sources can be implemented by following the contract in
`docs/adapter-contract.md` without modifying the core workflow.

Do not commit to specific future adapters in user-facing documentation.

---

## 9. What Must Not Break

When modifying this codebase, preserve the following invariants:

- `JOURNAL_HEADERS` column order and names (existing workbooks depend on this)
- `CONVERT_HEADERS` / `PROGRAM2_TSV_HEADERS` (TSV consumers depend on column positions)
- `adapter-contract.md` envelope shape (all adapters must return this structure)
- `main.status` vocabulary (controls fetch filtering and `--update` behavior)
- `validate-tsv` must not require database access

If structural changes to any of the above are necessary, treat them as
breaking changes and coordinate explicitly.

---

## 10. Documentation Map

### User Documentation

| File | Language | Content |
|---|---|---|
| `README.md` | English | Overview, quick start, command reference |
| `README-ja.md` | Japanese | 日本語版 README |
| `docs/workflow.md` | English | Step-by-step workflow guide |
| `docs/workflow-ja.md` | Japanese | 運用手順書（日本語） |

### Developer Documentation

| File | Content |
|---|---|
| `docs/adapter-contract.md` | Adapter interface specification (envelope, candidate fields, status vocabulary); convert sheet and TSV export summary |
| `docs/sinta-adapter-design.md` | SINTA adapter implementation design; `sinta-full-cli-v3` integration |
| `docs/grade-and-source-policy.md` | `grade` / `metric_source` classification policy |
