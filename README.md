# Journal Metrics Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![README 日本語](https://img.shields.io/badge/README-日本語-green.svg)](README-ja.md)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20809346.svg)](https://doi.org/10.5281/zenodo.20809346)

A workbook-based CLI tool for collecting, reviewing, reconciling, and exporting
journal-related information from multiple sources.

> **日本語版**: [README-ja.md](README-ja.md)

---

## Overview

**Journal Metrics Tools** is a workbook-based CLI tool for collecting, reviewing,
reconciling, and exporting journal-related information from multiple sources.

The tool uses an adapter-based architecture that supports different types of sources,
including bibliographic metadata sources and external journal assessment sources.
SEALIB and SINTA are the currently implemented adapters, but the design is intentionally
extensible — additional sources can be integrated without changing the core workflow.

A typical workflow:

1. Maintain a list of academic journals in an Excel workbook (`main` sheet)
2. Collect journal metadata and evaluation information via adapters (e.g. SEALIB for
   identifier enrichment, SINTA for accreditation rankings)
3. Review and confirm candidates in the `journal` sheet
4. Generate a validated TSV file for downstream database import

The current deployment uses SEALIB's data structure conventions — SEALIB (Southeast
Asian Periodicals Database, https://sealib.cseas.kyoto-u.ac.jp/) provides bibliographic
and holding information on Southeast Asian periodicals. TSV column names such as
`sealib_name` and `sealib_id` reflect these conventions. The SEALIB adapter is optional:
the SINTA fetch, convert, and export pipeline works without it.

- `main.issn` / `main.eissn` are optional. They are used as disambiguation hints when
  multiple SINTA candidates share the same title. SINTA search runs even without them,
  but unresolvable cases are marked `multiple_candidates`.
- `main.id` is not used during fetch. It is written to the `sealib_id` column at
  convert / export time. If `main.id` is empty, `sealib_id` is also empty. Running
  the SEALIB adapter can fill this field automatically.

---

## Features

| Command | Description |
|---|---|
| `template` | Create a structured Excel workbook with pre-defined sheets |
| `fetch-journal` | Collect journal metadata or evaluation information via adapters (SEALIB / SINTA / mock) |
| `convert` | Generate export-ready rows from accepted candidates |
| `export-tsv` | Export confirmed rows as a TSV file |
| `validate-tsv` | Validate TSV structure and field requirements |

**Adapter roles:**

| Adapter | Role | What it provides |
|---|---|---|
| `sealib` | Metadata enrichment | Supplements `main.id` / `main.issn` / `main.o_name` from a SEALIB SQLite database (optional) |
| `sinta` | Evaluation information | Fetches SINTA journal accreditation rankings via [`sinta-full-cli-v3`](https://github.com/kimipooh/sinta-full-cli-v3) (external CLI) |
| `mock` | Testing / validation | Returns fixed responses; no external tools required |

- `--update` flag: re-fetch previously processed records

The adapter architecture allows additional metadata or evaluation sources to be integrated in the future.

---

## Architecture

```
Workbook (main sheet)
  ↓
Adapters
  ├─ SEALIB  (metadata enrichment)
  ├─ SINTA   (evaluation information)
  └─ mock    (testing / validation)
  ↓
Review (journal sheet — candidate confirmation)
  ↓
Convert (convert sheet — export-ready rows)
  ↓
Validated TSV
```

> Downstream import into SEALIB or any other database is outside the scope of this repository.

---

## Requirements

- Python 3.11+
- `openpyxl >= 3.1, < 4` (installed via `requirements.txt`)
- **For SINTA fetch only**: [`sinta-full-cli-v3`](https://github.com/kimipooh/sinta-full-cli-v3) (separate repository)
- **For SEALIB identifier supplement (optional)**: SEALIB SQLite database file (read-only access)

---

## Installation

```bash
git clone <this-repo-url>
cd journal-metrics-tools

python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

For SINTA support, set up the SINTA CLI tool alongside this repository:

```bash
cd ..
git clone https://github.com/kimipooh/sinta-full-cli-v3
cd sinta-full-cli-v3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected directory layout:

```
research-tools/
├── journal-metrics-tools/          # this repository
│   ├── journal_metrics.py
│   └── ...
└── sinta-full-cli-v3/              # SINTA CLI (separate repo, needed only for SINTA fetch)
    └── sinta-full-cli-v3.py
```

---

## Quick Start (mock adapter — no external tools required)

```bash
# 1. Create a new workbook
python journal_metrics.py template --output my_journals.xlsx

# 2. Open my_journals.xlsx and fill in the `main` sheet:
#    * Required    = needed for the workflow (not enforced by code validation)
#    * Recommended = improves matching accuracy
#    * Optional    = may be omitted
#
#    Required:
#      name         — primary key for journal matching (must be filled in normal use)
#                     when using the SEALIB adapter, match the exact name in the SEALIB DB
#      status       — leave blank or set to "pending"
#    Recommended:
#      search_query — search string passed to SINTA / other external adapters
#      issn         — Print ISSN (disambiguation hint; search runs without it)
#      eissn        — Online ISSN (disambiguation hint; search runs without it)
#    Optional:
#      o_name       — original-language name
#      id           — SEALIB DB internal ID (written as sealib_id at convert/export time)

# 3. Fetch candidates using the built-in mock adapter
python journal_metrics.py fetch-journal --input my_journals.xlsx --adapter mock

# 4. Generate convert rows from accepted candidates
python journal_metrics.py convert --input my_journals.xlsx

# 5. Export to TSV and validate
python journal_metrics.py export-tsv --input my_journals.xlsx --output output.tsv
python journal_metrics.py validate-tsv --input output.tsv
```

---

## SINTA Workflow

```bash
# Step 1 (optional): supplement main.id / main.issn from SEALIB DB
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sealib \
    --db-path /path/to/sealib.sqlite \
    --country Indonesia        # optional country filter

# Step 2: fetch SINTA evaluation data
#   Note: each journal lookup takes approximately 30–60 seconds
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sinta \
    --sinta-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
    --sinta-python  ../sinta-full-cli-v3/.venv/bin/python

# Step 3: convert, export, and validate
python journal_metrics.py convert   --input my_journals.xlsx
python journal_metrics.py export-tsv --input my_journals.xlsx --output output.tsv
python journal_metrics.py validate-tsv --input output.tsv
```

See [docs/workflow.md](docs/workflow.md) for a detailed step-by-step guide including
main sheet column descriptions and candidate review.

---

## Update Workflow

```bash
# Re-fetch SINTA evaluation data for all non-terminal rows (skips status=skip/done)
python journal_metrics.py fetch-journal \
    --input my_journals.xlsx \
    --adapter sinta \
    --update \
    --sinta-command ../sinta-full-cli-v3/sinta-full-cli-v3.py \
    --sinta-python  ../sinta-full-cli-v3/.venv/bin/python

# Regenerate convert rows with updated evaluation data and re-export
python journal_metrics.py convert   --input my_journals.xlsx
python journal_metrics.py export-tsv --input my_journals.xlsx --output output.tsv
python journal_metrics.py validate-tsv --input output.tsv
```

`--update` replaces existing `journal` rows for the same adapter and main row,
so old evaluation data does not accumulate alongside new results.

---

## Command Reference

### `template`

```
python journal_metrics.py template --output OUTPUT
```

Creates a new Excel workbook with four sheets: `README`, `main`, `journal`, `convert`.

---

### `fetch-journal`

```
python journal_metrics.py fetch-journal --input INPUT --adapter ADAPTER [options]
```

| Option | Required | Description |
|---|---|---|
| `--input` | yes | `.xlsx` path (updated in place) |
| `--adapter` | yes | `mock` / `sealib` / `sinta` |
| `--update` | no | Re-fetch rows with status `fetched` / `not_found` / `multiple_candidates`; skips `skip` / `done` |
| `--db-path` | with sealib | SEALIB SQLite database path |
| `--country` | no | Country filter for SEALIB search (e.g. `Indonesia`) |
| `--sinta-command` | with sinta | Path to `sinta-full-cli-v3.py` |
| `--sinta-python` | no | Python interpreter for SINTA CLI (defaults to current) |
| `--sinta-timeout` | no | Subprocess timeout in seconds |

**`sealib` adapter specifics:**

- Searches SEALIB `header` table using `main.name` (falls back to `main.o_name`)
- If exactly one match is found, supplements empty `main.id` / `main.issn` / `main.o_name`
- Does **not** change `main.status` — rows remain `pending` for subsequent SINTA fetch
- Does **not** overwrite existing values or `main.name`

**`sinta` adapter specifics:**

- Searches SINTA using `main.search_query` (falls back to `main.journal_name`)
- When multiple candidates share an identical title, ISSN-based disambiguation is applied automatically
- `main.status` transitions: `pending` → `fetched` / `not_found` / `multiple_candidates` / `adapter_error`

---

### `convert`

```
python journal_metrics.py convert --input INPUT
```

Reads `journal` rows with `fetch_status = ok` and generates `convert` sheet rows.

| `journal_type` | grade present | `convert_status` | Included in TSV |
|---|---|---|---|
| `SINTA` | yes | `ready` | yes |
| `SINTA` | no | `hold` | no |
| `SEALIB`, `MOCK` | — | `skipped` | no |

`convert` always regenerates all rows from scratch — no accumulation of stale rows.

---

### `export-tsv`

```
python journal_metrics.py export-tsv --input INPUT --output OUTPUT
```

Exports `convert_status = ready` rows to a tab-separated TSV file.
Existing output files are overwritten.

---

### `validate-tsv`

```
python journal_metrics.py validate-tsv --input INPUT
```

Validates TSV structure without accessing any database.

- Checks column count and header names
- Checks that at least one of `sealib_name` / `sealib_o_name` / `sealib_id` is present per row
- Reports `errors` (blocking) and `warnings` (advisory)
- `errors = 0` is required before proceeding to database import

---

## Limitations

- **SINTA fetch speed**: Each journal lookup calls an external CLI subprocess and takes approximately 30–60 seconds. Plan accordingly for large batches.
- **TSV output format**: Column names (`sealib_name`, `sealib_id`, etc.) reflect SEALIB field conventions. Passing the TSV to a downstream import tool is outside the scope of this tool.
- **`enrich-db` command**: Planned but not yet implemented.
- **SEALIB adapter**: Reads from a local SQLite file only. No REST API or network access.
- **No GUI**: Command-line only. The Excel workbook is the managed data store; it is not intended as a display or reporting tool.

---

## Documentation

| Document | Language | Description |
|---|---|---|
| [README-ja.md](README-ja.md) | Japanese | 日本語版 README |
| [docs/workflow.md](docs/workflow.md) | English | Detailed step-by-step workflow guide |
| [docs/workflow-ja.md](docs/workflow-ja.md) | Japanese | 詳細な運用手順（日本語） |
| [docs/adapter-contract.md](docs/adapter-contract.md) | Japanese | Adapter contract specification (developer reference) |

---

## Author

Kimiya Kitani<br>
Center for Southeast Asian Studies, Kyoto University

---

## Citation

If you use this tool in your research, please cite it as follows:

```
Kitani, Kimiya. (2026). Journal Metrics Tools (Version 1.0.2) [Software]. Zenodo. https://doi.org/10.5281/zenodo.20809346
```

A `CITATION.cff` file is included in this repository for use with citation managers.

---

## License

MIT License. Copyright (c) 2026 Kimiya Kitani. See [LICENSE](LICENSE).
