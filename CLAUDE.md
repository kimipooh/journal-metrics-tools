# CLAUDE.md — Journal Metrics Tools

Development constraints for Claude Code, Codex, and contributors.
For design intent and architecture, see AGENT.md.

---

## 1. Project Context

Journal Metrics Tools is a workbook-based CLI for collecting, reviewing,
and exporting journal-related information from multiple sources.

Responsibility ends at validated TSV output. Downstream import is out of scope.

**Core commands:** `template` → `fetch-journal` → `convert` → `export-tsv` → `validate-tsv`

---

## 2. Workbook Compatibility Rules

The following constants define the Excel workbook structure.
Existing workbooks in production depend on column names and order.

| Constant | File | Risk if changed |
|---|---|---|
| `JOURNAL_HEADERS` | `journal_metrics.py` | Breaks all existing `journal` sheets |
| `CONVERT_HEADERS` | `journal_metrics.py` | Breaks all existing `convert` sheets + TSV consumers |
| `PROGRAM2_TSV_HEADERS` | `journal_metrics.py` | Breaks TSV column alignment |

**Rules:**

- Do not rename columns
- Do not reorder columns
- Do not silently remove columns
- If a column change is necessary, document a migration plan before touching code

---

## 3. Status Vocabulary Rules

`main.status` controls fetch filtering and `--update` behavior throughout the pipeline.

**Defined values:**

```
[blank] / pending  →  not yet fetched
fetched            →  one candidate confirmed
not_found          →  no candidates
multiple_candidates →  disambiguation failed
adapter_error      →  adapter call failed
skip               →  excluded from all fetches permanently
done               →  excluded from --update
```

**`journal.fetch_status`:** `ok` / `none` / `multiple` / `error`

**`convert.convert_status`:** `ready` / `hold` / `skipped`

**Rules:**

- Do not add new status values without full design review
- Do not change the semantics of existing values
- `should_process_main_row()` and `--update` logic depend on these values; changing vocabulary breaks filtering silently

---

## 4. Adapter Contract Rules

All adapters must conform to the interface defined in `docs/adapter-contract.md`.

**Envelope schema (required):**

```python
{
    "status": "fetched | not_found | multiple_candidates | adapter_error",
    "source": str,
    "query": str,
    "candidates": list,
    "error": str | None,
}
```

**Candidate schema (required fields):**

`source`, `external_journal_id`, `title`, `grade`, `url` — see contract for nullability rules.

**Rules:**

- Adapters must not perform Excel I/O
- Adapters must not access `main_row_id`; that is assigned by `fetch-journal`
- Do not add adapter-specific fields outside `raw_json`
- Do not bypass the contract for convenience; fix the contract instead

---

## 5. Convert Rules

`convert` performs **full regeneration** on every run:

1. Delete all data rows from `convert` sheet
2. Rebuild from `journal` rows where `fetch_status = ok`

This is intentional. Do not change `convert` to incremental/append mode without explicit design decision.

**convert_status assignment logic (must be preserved):**

```
SINTA / THAI_TIER  +  grade present  →  ready
SINTA / THAI_TIER  +  grade absent   →  hold
SEALIB / MOCK                        →  skipped
```

If this logic changes, update `docs/adapter-contract.md` and `docs/grade-and-source-policy.md` in the same commit.

---

## 6. --update Rules

`--update` means: **re-fetch previously processed records**.

**Scope:** rows with `status` not in `{skip, done}`

**Effect for SINTA:** existing `journal` rows for the same `main_row_id` and `journal_type` are deleted before writing new results.

**Rules:**

- `--update` is not annual-only; it re-fetches whenever called
- Do not change `--update` to target only specific adapters without design review
- SEALIB rows are not deleted by `--update` (only SINTA rows are currently deleted)

---

## 7. Adapter Roles

Do not conflate adapter roles in code or documentation.

| Adapter | Role |
|---|---|
| `sealib` | Metadata enrichment only — supplements `main.id` / `main.issn` / `main.o_name` |
| `sinta` | Evaluation information — accreditation rankings |
| `mock` | Fixed responses for testing; no external dependencies |

SEALIB adapter must not change `main.status` (rows remain `pending` for subsequent SINTA fetch).
SEALIB `journal` rows must always produce `convert_status = skipped`.

---

## 8. Responsibility Boundary

**In scope:**

- Excel workbook management (`main`, `journal`, `convert` sheets)
- Adapter execution and result mapping
- `convert` row generation
- TSV export and structural validation

**Out of scope — do not implement or reference in user-facing code:**

- SEALIB Program2 (`03-2-import-metrics.php`)
- PHP import scripts
- Writing to the SEALIB database
- REST API or web interface
- `enrich-db` command (planned, not yet implemented — do not add prematurely)

---

## 9. SEALIB Identifier Convention

`convert_sealib_id()` resolves `sealib_id` as follows:

- `metric_source == "SEALIB"` → use `journal.external_journal_id` (SEALIB internal `header.id`)
- Other sources → use `main.id`

This asymmetry is documented in `docs/adapter-contract.md` (naming discrepancy note).
Do not change this logic without updating that note and verifying existing workbooks.

---

## 10. Testing

When modifying `journal_metrics.py` or any adapter:

```bash
# Structural check
python3 -m py_compile journal_metrics.py

# Unit tests
python3 -m unittest discover -s tests

# Whitespace check
git diff --check
```

Tests live in `tests/`. Do not delete or skip tests to make a change pass.

---

## 11. Documentation Rules

| File | Audience | Content |
|---|---|---|
| `README.md` / `README-ja.md` | End users | What the tool does, how to use it |
| `docs/workflow.md` / `workflow-ja.md` | End users | Step-by-step operational guide |
| `AGENT.md` | Developers / AI | Architecture, design principles, non-goals |
| `CLAUDE.md` | Claude / Codex | Change constraints, compatibility rules |

Do not add implementation-phase notes to README or workflow docs.
Do not add user-facing instructions to AGENT.md or CLAUDE.md.

When modifying README or workflow docs, verify English/Japanese consistency.
When modifying `adapter-contract.md`, verify consistency with `sinta-adapter-design.md`.

---

## 12. When Unsure

Before making a change, assess impact on:

1. **Workbook compatibility** — does this rename/reorder a column?
2. **Adapter contract** — does this change the envelope or candidate schema?
3. **Status vocabulary** — does this add or reinterpret a status value?
4. **convert logic** — does this change which rows become `ready` / `hold` / `skipped`?

If any answer is yes, document the decision before writing code.
Use `.codex/tasks/task-YYYYMMDD-HHMM.md` for non-trivial implementation tasks.
