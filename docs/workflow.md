# Workflow Guide

This document describes the step-by-step workflow for using Journal Metrics Tools
to collect journal bibliographic metadata and evaluation information, reconcile them
in an Excel workbook, and export a validated TSV file.

---

## Overview

```
template
  └─ create workbook
        ↓
  fill in main sheet (manual)
        ↓
  fetch-journal --adapter sealib   (optional: supplement main.id / main.issn)
        ↓
  fetch-journal --adapter sinta    (fetch evaluation candidates)
        ↓
  review journal sheet             (manual: confirm or skip candidates)
        ↓
  convert                          (generate export rows)
        ↓
  export-tsv                       (write TSV file)
        ↓
  validate-tsv                     (validate before DB import)
        ↓
  [downstream import]              (outside this tool's scope)
```

---

## Step 1 — Create a workbook

```bash
python journal_metrics.py template --output my_journals.xlsx
```

Creates a new Excel workbook with four sheets:

| Sheet | Purpose |
|---|---|
| `README` | Auto-generated column descriptions |
| `main` | Human-edited journal list (input) |
| `journal` | Fetched candidates (written by `fetch-journal`) |
| `convert` | Export-ready rows (written by `convert`) |

---

## Step 2 — Fill in the `main` sheet

Open `my_journals.xlsx` and edit the `main` sheet.

### Column reference

| Column | Required | Description |
|---|---|---|
| `name` | **Required** | Primary journal name. Appears as `sealib_name` in TSV output. If using the SEALIB adapter, set this to the exact registered `header.name` in the SEALIB database. |
| `status` | **Required** | Leave blank or set to `pending` for new rows. |
| `o_name` | Optional | Original-language name (e.g. Indonesian title). |
| `id` | Optional | SEALIB `header.id`. Can be left blank; SEALIB adapter will supplement if found. |
| `issn` | Optional | Print ISSN. Used for SINTA ISSN-based disambiguation when multiple candidates share the same title. |
| `eissn` | Optional | Electronic ISSN. Also used for SINTA disambiguation. |
| `journal_name` | Optional | Display name from the external source. Used as fallback search key if `search_query` is empty. |
| `search_query` | Optional | Search string passed to external adapters (SINTA etc.). Takes priority over `journal_name`. SEALIB adapter does not use this column. |
| `note` | Optional | Free-text remarks. |

### Key rules

- `name` is used as the journal name key for SEALIB database matching. If you use the SEALIB adapter, set it to the exact registered `header.name`.
- `search_query` is the SINTA search term. It can differ from `name` (e.g. abbreviated title without publisher suffix).
- `main.name` is never overwritten by any adapter.
- Rows with `status = skip` or `done` are excluded from all fetch operations.

---

## Step 3 — Supplement identifiers from SEALIB (optional)

This step reads a SEALIB (Southeast Asian Periodicals Database: https://sealib.cseas.kyoto-u.ac.jp/)
SQLite database and fills in empty `main.id`, `main.issn`, and `main.o_name` for rows
that can be uniquely matched. This step is optional — skip it if you do not have access
to a SEALIB database or if the identifier fields are already populated.

```bash
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sealib \
    --db-path /path/to/sealib.sqlite \
    --country Indonesia        # optional country filter
```

**What happens:**

- SEALIB `header` table is searched using `main.name` (falls back to `main.o_name`)
- If exactly **one** match is found, empty `main.id` / `main.issn` / `main.o_name` are filled
- `main.status` is **not changed** — rows remain `pending` for the subsequent SINTA fetch
- Existing values and `main.name` are never overwritten
- SEALIB results appear in the `journal` sheet with `journal_type = SEALIB`; these rows are always `skipped` by `convert` and do not appear in TSV output

**When to use:**

Use this step when `main.id` or `main.issn` are unknown and you have access to the SEALIB database. The filled-in ISSN is then used by the SINTA adapter for disambiguation.

---

## Step 4 — Fetch evaluation data from SINTA

This step calls the external `sinta-full-cli-v3` tool as a subprocess.

```bash
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sinta \
    --sinta-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
    --sinta-python  ../sinta-full-cli-v3/.venv/bin/python
```

**What happens:**

- Rows with `main.status` = blank / `pending` / `adapter_error` are processed
- Each row is searched by `main.search_query` (falls back to `main.journal_name`)
- Results are written to the `journal` sheet with `journal_type = SINTA`
- `main.status` is updated:

| Outcome | `main.status` |
|---|---|
| Exactly 1 candidate found | `fetched` |
| Multiple candidates (title match narrows to 1) | `fetched` |
| Multiple candidates (ISSN disambiguation resolves to 1) | `fetched` |
| Multiple candidates (unresolved) | `multiple_candidates` |
| 0 candidates | `not_found` |
| CLI error / timeout | `adapter_error` |

**Disambiguation logic:**

When SINTA returns multiple candidates with identical normalized titles, the adapter
automatically applies ISSN-based matching using `main.issn` / `main.eissn`. If basic
mode results lack ISSN data, detail mode is called once per ambiguous row to retrieve
ISSN values. If disambiguation still fails, the row stays `multiple_candidates`.

**Performance note:**

Each journal lookup takes approximately 30–60 seconds. For 22 journals, expect
11–22 minutes. The process can be interrupted and resumed; rows already set to
`fetched` / `not_found` are skipped on the next run (unless `--update` is used).

---

## Step 5 — Review the `journal` sheet

Open the workbook and review the `journal` sheet. For each row:

- `fetch_status = ok`: candidate was accepted. The row will be included in `convert`.
- `fetch_status = multiple`: multiple candidates remain; manual selection may be needed.
- `fetch_status = none`: no candidate found.
- `fetch_status = error`: adapter error; retry with `fetch-journal` again.

If a row needs to be permanently excluded from future fetches, set `main.status = skip`.
For rows considered complete, set `main.status = done`.

---

## Step 6 — Generate convert rows

```bash
python journal_metrics.py convert --input my_journals.xlsx
```

Reads `journal` rows with `fetch_status = ok` and writes `convert` sheet rows.

| `journal_type` | grade | `convert_status` | Notes |
|---|---|---|---|
| `SINTA` | present | `ready` | Included in TSV |
| `SINTA` | absent | `hold` | Excluded; investigate the source |
| `SEALIB`, `MOCK` | — | `skipped` | Reference/test only; excluded from TSV |

`convert` always regenerates all rows from scratch, so re-running it after an update will not leave stale rows.

---

## Step 7 — Export to TSV

```bash
python journal_metrics.py export-tsv --input my_journals.xlsx --output output.tsv
```

Exports `convert_status = ready` rows only. Existing output files are overwritten.

---

## Step 8 — Validate the TSV

```bash
python journal_metrics.py validate-tsv --input output.tsv
```

Checks TSV structure without accessing any database. Reports:

- **errors**: structural issues that must be fixed before import (e.g. wrong column count, missing required fields)
- **warnings**: advisory notices (e.g. empty optional fields)

**Requirement before proceeding to database import:**

```
errors = 0
```

Warnings do not block import but should be reviewed.

---

## Step 9 — Pass TSV to your downstream import tool

Once `validate-tsv` reports `errors = 0`, the TSV file is ready for import.

Passing the validated TSV to a downstream database import tool is **outside the scope of
Journal Metrics Tools**. Consult your database import workflow documentation for the next
steps.

---

## Update Workflow

When previously fetched evaluation data needs to be refreshed:

```bash
# Re-fetch all non-terminal rows
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sinta \
    --update \
    --sinta-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
    --sinta-python  ../sinta-full-cli-v3/.venv/bin/python

# Regenerate and re-export
python journal_metrics.py convert   --input my_journals.xlsx
python journal_metrics.py export-tsv --input my_journals.xlsx --output output.tsv
python journal_metrics.py validate-tsv --input output.tsv
```

`--update` processes rows with status `pending` / `fetched` / `not_found` /
`multiple_candidates` / `adapter_error`. Rows with `skip` or `done` are never touched.
Existing `SINTA` journal rows for each processed `main` row are deleted before writing
new results, preventing accumulation of stale evaluation data.

---

## Troubleshooting

### SINTA CLI not found

```
ERROR: --sinta-command is required when --adapter sinta
```

Check that `--sinta-command` points to the correct path of `sinta-full-cli-v3.py`.

### `adapter_error` rows after SINTA fetch

The SINTA CLI failed for these rows (timeout, network error, or path issue).
Re-run `fetch-journal --adapter sinta` without `--update`; rows with
`main.status = adapter_error` are automatically retried.

### `multiple_candidates` rows remain

SINTA returned more than one candidate and ISSN disambiguation could not resolve them.
Options:
1. Provide or correct `main.issn` / `main.eissn`, then re-run `fetch-journal`
2. Manually adjust `search_query` to a more specific term
3. Set `main.status = skip` to permanently exclude the row

### `validate-tsv` reports errors

Common causes:
- `sealib_name` (= `main.name`) is empty: fill in the `name` column in the `main` sheet
- Column count mismatch: re-run `export-tsv` to regenerate the file

### SEALIB adapter returns `not_found`

The `main.name` did not match any `header.name` in the SEALIB database.
Check for spelling differences or trailing punctuation. Try adjusting `main.name`
to match the registered form exactly, or add `main.o_name` as a secondary key.
