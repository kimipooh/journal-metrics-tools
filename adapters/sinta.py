"""SINTA adapter for the Journal Metrics adapter contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _candidate(
    *,
    source: str,
    external_journal_id: str | None,
    title: str,
    publisher: str | None,
    grade: str | None,
    url: str | None,
) -> dict[str, Any]:
    return {
        "source": source,
        "external_journal_id": external_journal_id,
        "title": title,
        "issn": None,
        "eissn": None,
        "publisher": publisher,
        "country": "ID",
        "grade": grade,
        "url": url,
        "note": None,
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
    if not text or text == "N/A":
        return None
    return text


def _candidate_from_record(record: dict[str, Any], source: str) -> dict[str, Any]:
    return _candidate(
        source=source,
        external_journal_id=_text_or_none(record.get("journal_id")),
        title=str(record.get("journal_name", "")).strip(),
        publisher=_text_or_none(record.get("affiliation")),
        grade=_text_or_none(record.get("sinta_level")),
        url=_text_or_none(record.get("profile_url")),
    )


def fetch_journal(
    query: str,
    source: str = "SINTA",
    command: str | None = None,
    python: str | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    """Fetch SINTA candidates through sinta-full-cli-v3.py."""
    normalized_query = query.strip()
    if not normalized_query:
        return _error_envelope(query, source, "query is required")

    if command is None or not str(command).strip():
        return _error_envelope(query, source, "command is required")

    command_path = Path(str(command)).expanduser()
    if not command_path.is_file():
        return _error_envelope(query, source, f"command does not exist: {command}")

    interpreter = python or sys.executable
    cmd = [
        interpreter,
        str(command_path),
        "-q",
        query,
        "-m",
        "title",
        "-f",
        "json",
        "--fetch-mode",
        "basic",
    ]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return _error_envelope(query, source, f"timeout after {timeout}s")
    except Exception as exc:
        return _error_envelope(query, source, str(exc))

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if completed.returncode != 0:
        error = stderr or stdout or f"command failed with return code {completed.returncode}"
        return _error_envelope(query, source, error)

    if not stdout:
        if stderr:
            return _error_envelope(query, source, stderr)
        return _envelope(
            status="not_found",
            source=source,
            query=query,
            candidates=[],
            error=None,
        )

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return _error_envelope(query, source, str(exc))

    if not isinstance(payload, list):
        return _error_envelope(query, source, "JSON payload must be a list")

    candidates: list[dict[str, Any]] = []
    for record in payload:
        if not isinstance(record, dict):
            return _error_envelope(query, source, "JSON list items must be objects")
        candidates.append(_candidate_from_record(record, source))

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
