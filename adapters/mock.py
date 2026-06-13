"""Mock adapter for the Journal Metrics adapter contract."""

from __future__ import annotations

from typing import Any


def _candidate(
    *,
    source: str,
    external_journal_id: str,
    title: str,
    issn: str | None,
    eissn: str | None,
    publisher: str | None,
    country: str | None,
    grade: str | None,
    url: str | None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "external_journal_id": external_journal_id,
        "title": title,
        "issn": issn,
        "eissn": eissn,
        "publisher": publisher,
        "country": country,
        "grade": grade,
        "url": url,
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


def fetch_journal(query: str, source: str = "MOCK") -> dict[str, Any]:
    """Return a fixed adapter-contract envelope without external access."""
    normalized_query = query.lower()
    title = query.strip() or "Mock Journal"

    if "multiple" in normalized_query:
        return _envelope(
            status="multiple_candidates",
            source=source,
            query=query,
            candidates=[
                _candidate(
                    source=source,
                    external_journal_id="MOCK-001",
                    title=f"{title} A",
                    issn="1111-2222",
                    eissn=None,
                    publisher="Mock Publisher A",
                    country="ZZ",
                    grade="Mock Grade 1",
                    url="https://example.invalid/mock/001",
                ),
                _candidate(
                    source=source,
                    external_journal_id="MOCK-002",
                    title=f"{title} B",
                    issn="3333-4444",
                    eissn="5555-6666",
                    publisher="Mock Publisher B",
                    country="ZZ",
                    grade="Mock Grade 2",
                    url="https://example.invalid/mock/002",
                ),
            ],
            error=None,
        )

    if "notfound" in normalized_query:
        return _envelope(
            status="not_found",
            source=source,
            query=query,
            candidates=[],
            error=None,
        )

    if "error" in normalized_query:
        return _envelope(
            status="adapter_error",
            source=source,
            query=query,
            candidates=[],
            error="Mock adapter error",
        )

    return _envelope(
        status="fetched",
        source=source,
        query=query,
        candidates=[
            _candidate(
                source=source,
                external_journal_id="MOCK-000",
                title=title,
                issn="1234-5678",
                eissn="8765-4321",
                publisher="Mock Publisher",
                country="ZZ",
                grade="Mock Grade",
                url="https://example.invalid/mock/000",
            )
        ],
        error=None,
    )

