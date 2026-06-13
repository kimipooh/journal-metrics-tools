"""Map adapter envelopes to journal sheet row dictionaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


FETCH_STATUS_BY_ENVELOPE_STATUS = {
    "fetched": "ok",
    "multiple_candidates": "multiple",
    "not_found": "none",
    "adapter_error": "error",
}


def _raw_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def _fetched_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_from_candidate(
    *,
    candidate: dict[str, Any],
    main_row_id: int,
    fetch_status: str,
    fetched_at: str,
) -> dict[str, Any]:
    return {
        "main_row_id": main_row_id,
        "journal_type": candidate.get("source"),
        "external_journal_id": candidate.get("external_journal_id"),
        "journal_name": candidate.get("title"),
        "affiliation": candidate.get("publisher"),
        "grade": candidate.get("grade"),
        "profile_url": candidate.get("url"),
        "fetch_status": fetch_status,
        "fetched_at": fetched_at,
        "raw_json": _raw_json(candidate),
    }


def _row_from_envelope(
    *,
    envelope: dict[str, Any],
    main_row_id: int,
    fetch_status: str,
    fetched_at: str,
) -> dict[str, Any]:
    return {
        "main_row_id": main_row_id,
        "journal_type": envelope.get("source"),
        "external_journal_id": None,
        "journal_name": envelope.get("query"),
        "affiliation": None,
        "grade": None,
        "profile_url": None,
        "fetch_status": fetch_status,
        "fetched_at": fetched_at,
        "raw_json": _raw_json(envelope),
    }


def map_envelope_to_journal_rows(
    envelope: dict[str, Any],
    main_row_id: int,
) -> list[dict[str, Any]]:
    """Convert an adapter envelope into journal sheet row dictionaries."""
    status = envelope.get("status")
    if status not in FETCH_STATUS_BY_ENVELOPE_STATUS:
        raise ValueError(f"Unsupported envelope status: {status!r}")

    fetch_status = FETCH_STATUS_BY_ENVELOPE_STATUS[status]
    fetched_at = _fetched_at()
    candidates = envelope.get("candidates") or []

    if status in {"not_found", "adapter_error"}:
        return [
            _row_from_envelope(
                envelope=envelope,
                main_row_id=main_row_id,
                fetch_status=fetch_status,
                fetched_at=fetched_at,
            )
        ]

    return [
        _row_from_candidate(
            candidate=candidate,
            main_row_id=main_row_id,
            fetch_status=fetch_status,
            fetched_at=fetched_at,
        )
        for candidate in candidates
    ]


def row_to_journal_values(row: dict[str, Any], headers: list[str]) -> list[Any]:
    """Return row values ordered by the supplied journal headers."""
    return [row.get(header) for header in headers]
