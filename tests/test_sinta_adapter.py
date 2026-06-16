from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters import sinta


def _record(
    title: str,
    journal_id: str,
    p_issn: str | None = None,
    e_issn: str | None = None,
) -> dict[str, str]:
    record = {
        "journal_name": title,
        "sinta_level": "S2 Accredited",
        "affiliation": "Publisher",
        "journal_id": journal_id,
        "profile_url": f"https://example.test/{journal_id}",
    }
    if p_issn is not None:
        record["p_issn"] = p_issn
    if e_issn is not None:
        record["e_issn"] = e_issn
    return record


class SintaAdapterCandidateSelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.command = Path(self.temp_dir.name) / "sinta-full-cli-v3.py"
        self.command.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _completed(self, records: list[dict[str, str]]) -> sinta.subprocess.CompletedProcess:
        return sinta.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(records),
            stderr="",
        )

    def _fetch_with_payload(
        self,
        query: str,
        records: list[dict[str, str]],
        *,
        main_issn: str | None = None,
        main_eissn: str | None = None,
        detail_records: list[dict[str, str]] | None = None,
    ) -> tuple[dict, int]:
        completed = sinta.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(records),
            stderr="",
        )
        if detail_records is None:
            side_effect = None
            return_value = completed
        else:
            side_effect = [completed, self._completed(detail_records)]
            return_value = None
        with patch(
            "adapters.sinta.subprocess.run",
            return_value=return_value,
            side_effect=side_effect,
        ) as run:
            envelope = sinta.fetch_journal(
                query,
                command=str(self.command),
                main_issn=main_issn,
                main_eissn=main_eissn,
            )
        return envelope, run.call_count

    def test_unique_exact_title_match_is_fetched_from_multiple_candidates(self) -> None:
        envelope, call_count = self._fetch_with_payload(
            "Masyarakat Indonesia",
            [
                _record("Media Kesehatan Masyarakat Indonesia", "1"),
                _record("Masyarakat Indonesia", "2"),
            ],
        )

        self.assertEqual(call_count, 1)
        self.assertEqual(envelope["status"], "fetched")
        self.assertEqual(len(envelope["candidates"]), 1)
        self.assertEqual(envelope["candidates"][0]["title"], "Masyarakat Indonesia")

    def test_exact_title_match_uses_case_space_and_trailing_period_normalization(self) -> None:
        envelope, call_count = self._fetch_with_payload(
            "  Masyarakat   Indonesia. ",
            [
                _record("Media Kesehatan Masyarakat Indonesia", "1"),
                _record("masyarakat indonesia", "2"),
            ],
        )

        self.assertEqual(call_count, 1)
        self.assertEqual(envelope["status"], "fetched")
        self.assertEqual(envelope["candidates"][0]["external_journal_id"], "2")

    def test_multiple_candidates_without_exact_match_stay_multiple(self) -> None:
        envelope, _call_count = self._fetch_with_payload(
            "Masyarakat Indonesia",
            [
                _record("Media Kesehatan Masyarakat Indonesia", "1"),
                _record("Jurnal Masyarakat Indonesia Baru", "2"),
            ],
        )

        self.assertEqual(envelope["status"], "multiple_candidates")
        self.assertEqual(len(envelope["candidates"]), 2)

    def test_multiple_exact_matches_stay_multiple_without_issn(self) -> None:
        envelope, call_count = self._fetch_with_payload(
            "Masyarakat Indonesia",
            [
                _record("Masyarakat Indonesia", "1"),
                _record("masyarakat   indonesia.", "2"),
            ],
        )

        self.assertEqual(call_count, 1)
        self.assertEqual(envelope["status"], "multiple_candidates")
        self.assertEqual(len(envelope["candidates"]), 2)

    def test_single_candidate_remains_fetched(self) -> None:
        envelope, call_count = self._fetch_with_payload(
            "Masyarakat Indonesia",
            [_record("Media Kesehatan Masyarakat Indonesia", "1")],
            main_issn="1234-5678",
        )

        self.assertEqual(call_count, 1)
        self.assertEqual(envelope["status"], "fetched")
        self.assertEqual(len(envelope["candidates"]), 1)

    def test_multiple_exact_matches_with_one_basic_issn_match_is_fetched(self) -> None:
        envelope, call_count = self._fetch_with_payload(
            "Indonesian Journal of Geography",
            [
                _record(
                    "INDONESIAN JOURNAL OF GEOGRAPHY",
                    "1",
                    p_issn="0024-9521",
                    e_issn="2354-9114",
                ),
                _record(
                    "INDONESIAN JOURNAL OF GEOGRAPHY",
                    "2",
                    p_issn="0024-9521",
                    e_issn="2354-911",
                ),
            ],
            main_eissn="23549114",
        )

        self.assertEqual(call_count, 1)
        self.assertEqual(envelope["status"], "fetched")
        self.assertEqual(envelope["candidates"][0]["external_journal_id"], "1")

    def test_multiple_exact_matches_with_one_detail_issn_match_is_fetched(self) -> None:
        envelope, call_count = self._fetch_with_payload(
            "Indonesian Journal of Geography",
            [
                _record("INDONESIAN JOURNAL OF GEOGRAPHY", "1"),
                _record("INDONESIAN JOURNAL OF GEOGRAPHY", "2"),
            ],
            main_eissn="23549114",
            detail_records=[
                _record(
                    "INDONESIAN JOURNAL OF GEOGRAPHY",
                    "1",
                    p_issn="00249521",
                    e_issn="23549114",
                ),
                _record(
                    "INDONESIAN JOURNAL OF GEOGRAPHY",
                    "2",
                    p_issn="00249521",
                    e_issn="2354911",
                ),
            ],
        )

        self.assertEqual(call_count, 2)
        self.assertEqual(envelope["status"], "fetched")
        self.assertEqual(envelope["candidates"][0]["external_journal_id"], "1")
        self.assertEqual(envelope["candidates"][0]["eissn"], "23549114")

    def test_multiple_exact_matches_with_no_issn_match_stay_multiple(self) -> None:
        envelope, call_count = self._fetch_with_payload(
            "Masyarakat Indonesia",
            [
                _record("Masyarakat Indonesia", "1", p_issn="1111-1111"),
                _record("masyarakat   indonesia.", "2", e_issn="2222-2222"),
            ],
            main_issn="3333-3333",
        )

        self.assertEqual(call_count, 1)
        self.assertEqual(envelope["status"], "multiple_candidates")
        self.assertEqual(len(envelope["candidates"]), 2)

    def test_multiple_exact_matches_with_two_issn_matches_stay_multiple(self) -> None:
        envelope, call_count = self._fetch_with_payload(
            "Masyarakat Indonesia",
            [
                _record("Masyarakat Indonesia", "1", p_issn="1111-1111"),
                _record("masyarakat   indonesia.", "2", e_issn="1111-1111"),
            ],
            main_issn="11111111",
        )

        self.assertEqual(call_count, 1)
        self.assertEqual(envelope["status"], "multiple_candidates")
        self.assertEqual(len(envelope["candidates"]), 2)

    def test_detail_failure_keeps_basic_multiple_candidates(self) -> None:
        basic = self._completed(
            [
                _record("Masyarakat Indonesia", "1"),
                _record("masyarakat   indonesia.", "2"),
            ]
        )
        detail_failure = sinta.subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="detail failed",
        )

        with patch(
            "adapters.sinta.subprocess.run",
            side_effect=[basic, detail_failure],
        ) as run:
            envelope = sinta.fetch_journal(
                "Masyarakat Indonesia",
                command=str(self.command),
                main_issn="1111-1111",
            )

        self.assertEqual(run.call_count, 2)
        self.assertEqual(envelope["status"], "multiple_candidates")
        self.assertEqual(len(envelope["candidates"]), 2)

    def test_detail_mode_is_not_called_for_unique_exact_title_match(self) -> None:
        completed = self._completed(
            [
                _record("Media Kesehatan Masyarakat Indonesia", "1"),
                _record("Masyarakat Indonesia", "2"),
            ]
        )
        with patch("adapters.sinta.subprocess.run", return_value=completed) as run:
            envelope = sinta.fetch_journal(
                "Masyarakat Indonesia",
                command=str(self.command),
                main_issn="1111-1111",
            )

        self.assertEqual(run.call_count, 1)
        self.assertNotIn("detail", run.call_args.args[0])
        self.assertEqual(envelope["status"], "fetched")

    def test_adapter_error_retry_status_path_is_unchanged(self) -> None:
        completed = sinta.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="Error: failed to retrieve SINTA search results",
        )
        with patch("adapters.sinta.subprocess.run", return_value=completed):
            envelope = sinta.fetch_journal("Masyarakat Indonesia", command=str(self.command))

        self.assertEqual(envelope["status"], "adapter_error")
        self.assertEqual(envelope["candidates"], [])


if __name__ == "__main__":
    unittest.main()
