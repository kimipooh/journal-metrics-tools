# Changelog

All notable changes to this project will be documented in this file.

This format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.2] - 2026-06-23

Documentation and DOI metadata update. No functional changes.

### Changed

- Clarified the roles of `main` sheet fields in the documentation (required / recommended / optional)
- Documented `main.issn` / `main.eissn` as optional disambiguation hints for SINTA matching; SINTA fetch works without them
- Documented the role of `main.id` in convert/export workflows and `sealib_id` generation
- Updated the citation and `CITATION.cff` metadata for v1.0.2

### Removed

- Removed a tracked generated workbook (`journal_metrics.xlsx`) and aligned repository contents with `.gitignore`

## [1.0.1] - 2026-06-16

Zenodo integration and citation metadata update. No functional changes.

### Added

- Zenodo DOI badge in `README.md` / `README-ja.md`
- `CITATION.cff` citation metadata file
- Citation section in `README.md` / `README-ja.md`

## [1.0.0] - 2026-06-16

### Added

**Core workflow commands:**

- `template` — Create a structured Excel workbook with pre-defined sheets (`main`, `journal`, `convert`)
- `fetch-journal` — Collect journal metadata or evaluation information via adapters (SEALIB / SINTA / mock)
- `convert` — Generate export-ready rows from accepted candidates in the `journal` sheet
- `export-tsv` — Export confirmed `convert` rows as a TSV file
- `validate-tsv` — Validate TSV structure and field requirements

**Adapter architecture:**

- `sealib` adapter — Metadata enrichment; supplements `main.id` / `main.issn` / `main.o_name` from a SEALIB SQLite database (optional)
- `sinta` adapter — Evaluation information; fetches SINTA journal accreditation rankings via `sinta-full-cli-v3` (external CLI)
- `mock` adapter — Fixed responses for testing and validation; no external dependencies

**Update workflow:**

- `--update` flag for `fetch-journal` — re-fetches previously processed records (rows not in `{skip, done}`)
- SINTA rows for the same `main_row_id` and `journal_type` are replaced on update

**Validation workflow:**

- `validate-tsv` structural and field-level validation
- `export-ready` filtering via `convert_status`

**Status vocabulary:**

- `main.status`: `pending` / `fetched` / `not_found` / `multiple_candidates` / `adapter_error` / `skip` / `done`
- `journal.fetch_status`: `ok` / `none` / `multiple` / `error`
- `convert.convert_status`: `ready` / `hold` / `skipped`

### Architecture

Established workbook-centric pipeline:

```
Workbook (main sheet)
  ↓ fetch-journal
Adapter (SEALIB / SINTA / mock)
  ↓ review
journal sheet (candidate confirmation)
  ↓ convert
convert sheet (export-ready rows)
  ↓ export-tsv / validate-tsv
TSV output
```

Metadata enrichment (SEALIB) and evaluation information retrieval (SINTA) are intentionally separated adapter roles. SEALIB rows do not advance `main.status`; SINTA rows do.

`convert_status` assignment logic:

| Source | Grade present | convert_status |
|---|---|---|
| SINTA | yes | `ready` |
| SINTA | no | `hold` |
| SEALIB / MOCK | — | `skipped` |

### Documentation

User-facing documentation:

- `README.md` — English overview, commands, workflow, requirements
- `README-ja.md` — Japanese equivalent
- `docs/workflow.md` — Step-by-step operational guide (English)
- `docs/workflow-ja.md` — Step-by-step operational guide (Japanese)

Developer / AI documentation:

- `AGENT.md` — Architecture, design principles, non-goals
- `CLAUDE.md` — Change constraints, compatibility rules
- `docs/adapter-contract.md` — Envelope and candidate schema contract
- `docs/sinta-adapter-design.md` — SINTA adapter implementation notes
- `docs/grade-and-source-policy.md` — Grade and source classification policy

### Notes

**Explicitly out of scope for this project:**

- Database import processing (SEALIB Program2 / `03-2-import-metrics.php`)
- PHP import scripts
- SQLite write operations
- REST API or web interface
- `enrich-db` command (planned, not yet implemented)

The repository is responsible for producing validated TSV output only.
Downstream import into SEALIB or any other system is out of scope.

**External dependency:**

SINTA fetch requires [`sinta-full-cli-v3`](https://github.com/kimipooh/sinta-full-cli-v3) (separate repository).
SEALIB adapter requires a SEALIB SQLite database file (optional; read-only).

---

[1.0.2]: https://github.com/kimipooh/journal-metrics-tools/releases/tag/v1.0.2
[1.0.1]: https://github.com/kimipooh/journal-metrics-tools/releases/tag/v1.0.1
[1.0.0]: https://github.com/kimipooh/journal-metrics-tools/releases/tag/v1.0.0
