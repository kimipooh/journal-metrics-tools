"""SEALIB adapter for the Journal Metrics adapter contract."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import quote


DEFAULT_LIMIT = 20


def _candidate(
    *,
    source: str,
    external_journal_id: str | None,
    title: str,
    issn: str | None,
    country: str | None,
    note: str | None,
) -> dict[str, Any]:
    return {
        "source": source,
        "external_journal_id": external_journal_id,
        "title": title,
        "issn": issn,
        "eissn": None,
        "publisher": None,
        "country": country,
        "grade": None,
        "url": None,
        "note": note,
    }


def _envelope(
    *,
    status: str,
    source: str,
    query: str,
    candidates: list[dict[str, Any]],
    error: str | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "source": source,
        "query": query,
        "candidates": candidates,
        "error": error,
    }


def _error_envelope(query: str, source: str, error: str) -> dict[str, Any]:
    return _envelope(
        status="adapter_error",
        source=source,
        query=query,
        candidates=[],
        error=error,
    )


def _text_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _read_only_uri(db_path: str) -> str:
    resolved = Path(db_path).expanduser().resolve()
    return f"file:{quote(str(resolved), safe='/:')}?mode=ro"


def _fetch_header_rows(
    *,
    db_path: str,
    query: str,
    country: str | None,
    limit: int,
) -> list[sqlite3.Row]:
    uri = _read_only_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        like_query = f"%{query}%"
        params: list[object] = [like_query, like_query]
        where = "(name LIKE ? OR o_name LIKE ?)"
        if country:
            where += " AND UPPER(country) = UPPER(?)"
            params.append(country)
        params.append(limit)
        return conn.execute(
            f"""
            SELECT id, name, o_name, issn, country
              FROM header
             WHERE {where}
             ORDER BY id
             LIMIT ?
            """,
            params,
        ).fetchall()
    finally:
        conn.close()


def _candidate_from_row(row: sqlite3.Row, source: str) -> dict[str, Any] | None:
    title = _text_or_none(row["name"])
    if title is None:
        return None
    return _candidate(
        source=source,
        external_journal_id=_text_or_none(row["id"]),
        title=title,
        issn=_text_or_none(row["issn"]),
        country=_text_or_none(row["country"]),
        note=_text_or_none(row["o_name"]),
    )


def fetch_journal(
    query: str,
    source: str = "SEALIB",
    db_path: str | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    """Fetch SEALIB header candidates as an adapter-contract envelope.

    The SEALIB database is opened through a SQLite ``mode=ro`` URI and this
    adapter only issues SELECT statements.
    """
    if db_path is None or not str(db_path).strip():
        return _error_envelope(query, source, "db_path is required")

    normalized_query = query.strip()
    if not normalized_query:
        return _envelope(
            status="not_found",
            source=source,
            query=query,
            candidates=[],
            error=None,
        )

    try:
        rows = _fetch_header_rows(
            db_path=str(db_path),
            query=normalized_query,
            country=_text_or_none(country),
            limit=DEFAULT_LIMIT,
        )
        candidates = [
            candidate
            for row in rows
            if (candidate := _candidate_from_row(row, source)) is not None
        ]
    except Exception as exc:
        return _error_envelope(query, source, str(exc))

    if len(candidates) == 1:
        status = "fetched"
    elif len(candidates) > 1:
        status = "multiple_candidates"
    else:
        status = "not_found"

    return _envelope(
        status=status,
        source=source,
        query=query,
        candidates=candidates,
        error=None,
    )
