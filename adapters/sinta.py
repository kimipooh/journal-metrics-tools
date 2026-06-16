"""SINTA adapter for the Journal Metrics adapter contract."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _candidate(
    *,
    source: str,
    external_journal_id: str | None,
    title: str,
    issn: str | None,
    eissn: str | None,
    publisher: str | None,
    grade: str | None,
    url: str | None,
) -> dict[str, Any]:
    return {
        "source": source,
        "external_journal_id": external_journal_id,
        "title": title,
        "issn": issn,
        "eissn": eissn,
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


def _normalize_title_for_match(value: str) -> str:
    text = re.sub(r"\s+", " ", value.strip())
    text = text.rstrip(".").strip()
    return text.casefold()


def _normalize_issn_for_match(value: object) -> str | None:
    text = _text_or_none(value)
    if text is None:
        return None
    normalized = re.sub(r"[\s-]+", "", text).casefold()
    return normalized or None


def _candidate_issns(candidate: dict[str, Any]) -> set[str]:
    return {
        normalized
        for value in [candidate.get("issn"), candidate.get("eissn")]
        if (normalized := _normalize_issn_for_match(value)) is not None
    }


def _select_candidates_for_status(
    candidates: list[dict[str, Any]],
    query: str,
    main_issn: object = None,
    main_eissn: object = None,
) -> tuple[str, list[dict[str, Any]]]:
    if len(candidates) == 1:
        return "fetched", candidates
    if len(candidates) == 0:
        return "not_found", candidates

    normalized_query = _normalize_title_for_match(query)
    exact_matches = [
        candidate
        for candidate in candidates
        if _normalize_title_for_match(str(candidate.get("title", ""))) == normalized_query
    ]
    if len(exact_matches) == 1:
        return "fetched", exact_matches
    if len(exact_matches) >= 2:
        issn_matches = _issn_matches_for_exact_title(
            candidates,
            query,
            main_issn=main_issn,
            main_eissn=main_eissn,
        )
        if len(issn_matches) == 1:
            return "fetched", issn_matches
    return "multiple_candidates", candidates


def _main_issns(main_issn: object = None, main_eissn: object = None) -> set[str]:
    return {
        normalized
        for value in [main_issn, main_eissn]
        if (normalized := _normalize_issn_for_match(value)) is not None
    }


def _exact_title_matches(
    candidates: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    normalized_query = _normalize_title_for_match(query)
    return [
        candidate
        for candidate in candidates
        if _normalize_title_for_match(str(candidate.get("title", ""))) == normalized_query
    ]


def _issn_matches_for_exact_title(
    candidates: list[dict[str, Any]],
    query: str,
    main_issn: object = None,
    main_eissn: object = None,
) -> list[dict[str, Any]]:
    main_issns = _main_issns(main_issn, main_eissn)
    if not main_issns:
        return []
    return [
        candidate
        for candidate in _exact_title_matches(candidates, query)
        if main_issns & _candidate_issns(candidate)
    ]


def _should_fetch_detail_for_issn(
    candidates: list[dict[str, Any]],
    query: str,
    main_issn: object = None,
    main_eissn: object = None,
) -> bool:
    if not _main_issns(main_issn, main_eissn):
        return False
    exact_matches = _exact_title_matches(candidates, query)
    if len(exact_matches) < 2:
        return False
    if len(_issn_matches_for_exact_title(
        exact_matches,
        query,
        main_issn=main_issn,
        main_eissn=main_eissn,
    )) == 1:
        return False
    return any(not _candidate_issns(candidate) for candidate in exact_matches)


def _record_value(record: dict[str, Any], *keys: str) -> object:
    for key in keys:
        if key in record:
            return record.get(key)
    return None


def _candidate_from_record(record: dict[str, Any], source: str) -> dict[str, Any]:
    return _candidate(
        source=source,
        external_journal_id=_text_or_none(record.get("journal_id")),
        title=str(record.get("journal_name", "")).strip(),
        issn=_text_or_none(_record_value(record, "p_issn", "p-issn", "issn")),
        eissn=_text_or_none(_record_value(record, "e_issn", "e-issn", "eissn")),
        publisher=_text_or_none(record.get("affiliation")),
        grade=_text_or_none(record.get("sinta_level")),
        url=_text_or_none(record.get("profile_url")),
    )


def _sinta_command(
    *,
    interpreter: str,
    command_path: Path,
    query: str,
    fetch_mode: str,
) -> list[str]:
    return [
        interpreter,
        str(command_path),
        "-q",
        query,
        "-m",
        "title",
        "-f",
        "json",
        "--fetch-mode",
        fetch_mode,
    ]


def _run_sinta_cli(
    *,
    cmd: list[str],
    timeout: int,
) -> tuple[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "timeout", None
    except Exception as exc:
        return "error", str(exc)

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if completed.returncode != 0:
        return "error", stderr or stdout or f"command failed with return code {completed.returncode}"

    if not stdout:
        if stderr:
            return "error", stderr
        return "not_found", []

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return "error", str(exc)

    if not isinstance(payload, list):
        return "error", "JSON payload must be a list"

    for record in payload:
        if not isinstance(record, dict):
            return "error", "JSON list items must be objects"

    return "ok", payload


def _candidates_from_payload(payload: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    return [_candidate_from_record(record, source) for record in payload]


def fetch_journal(
    query: str,
    source: str = "SINTA",
    command: str | None = None,
    python: str | None = None,
    timeout: int = 180,
    main_issn: object = None,
    main_eissn: object = None,
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
    cmd = _sinta_command(
        interpreter=interpreter,
        command_path=command_path,
        query=query,
        fetch_mode="basic",
    )

    run_status, payload_or_error = _run_sinta_cli(cmd=cmd, timeout=timeout)

    if run_status == "timeout":
        return _error_envelope(query, source, f"timeout after {timeout}s")
    if run_status == "error":
        return _error_envelope(query, source, str(payload_or_error))
    if run_status == "not_found":
        return _envelope(
            status="not_found",
            source=source,
            query=query,
            candidates=[],
            error=None,
        )

    candidates = _candidates_from_payload(payload_or_error, source)

    status, candidates = _select_candidates_for_status(
        candidates,
        query,
        main_issn=main_issn,
        main_eissn=main_eissn,
    )
    if status == "multiple_candidates" and _should_fetch_detail_for_issn(
        candidates,
        query,
        main_issn=main_issn,
        main_eissn=main_eissn,
    ):
        detail_cmd = _sinta_command(
            interpreter=interpreter,
            command_path=command_path,
            query=query,
            fetch_mode="detail",
        )
        detail_status, detail_payload = _run_sinta_cli(
            cmd=detail_cmd,
            timeout=timeout,
        )
        if detail_status == "ok":
            detail_candidates = _candidates_from_payload(detail_payload, source)
            detail_selected = _issn_matches_for_exact_title(
                detail_candidates,
                query,
                main_issn=main_issn,
                main_eissn=main_eissn,
            )
            if len(detail_selected) == 1:
                status = "fetched"
                candidates = detail_selected

    return _envelope(
        status=status,
        source=source,
        query=query,
        candidates=candidates,
        error=None,
    )
