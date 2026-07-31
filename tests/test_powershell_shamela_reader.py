"""Tests for the Shamela .mdb PowerShell reader wrapper.

Mocks `subprocess.run` rather than invoking real 32-bit PowerShell/COM -
the actual PowerShell/ADODB integration was verified by hand against
real Shamela files (see CHANGELOG); these tests cover the Python-side
batching, JSON round-trip, and error-handling logic in isolation.
"""

import json
import subprocess
from pathlib import Path

import pytest

from islamic_research_hub.infrastructure.persistence.powershell_shamela_reader import (
    PowerShellShamelaReader,
    ShamelaReaderError,
)


def _fake_run_writing_results(results: list[dict]):
    """Return a fake `subprocess.run` that writes `results` to the
    `-ResultsFile` path it's called with as newline-delimited JSON,
    mimicking the real (fixed) script's streamed output format."""

    def _run(args, **kwargs):
        results_file = Path(args[args.index("-ResultsFile") + 1])
        results_file.write_text(
            "\n".join(json.dumps(result) for result in results), encoding="utf-8"
        )
        return subprocess.CompletedProcess(args, 0)

    return _run


def test_read_all_returns_empty_tuple_for_no_paths() -> None:
    """No paths means no subprocess call at all."""
    reader = PowerShellShamelaReader()

    assert reader.read_all(()) == ()


def test_read_all_parses_a_successful_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real, successful result parses into a ShamelaRawBook with its rows intact."""
    results = [
        {
            "Path": r"F:\shamela\Books\0\1.mdb",
            "Succeeded": True,
            "Error": None,
            "BookRows": [{"id": 1, "nass": "content", "page": 1, "part": 1}],
            "TitleRows": {"id": 1, "tit": "heading", "lvl": 1, "sub": 0},
        }
    ]
    monkeypatch.setattr(subprocess, "run", _fake_run_writing_results(results))
    reader = PowerShellShamelaReader()

    parsed = reader.read_all((Path(r"F:\shamela\Books\0\1.mdb"),))

    assert len(parsed) == 1
    book = parsed[0]
    assert book.succeeded is True
    assert book.error is None
    assert book.book_rows == ({"id": 1, "nass": "content", "page": 1, "part": 1},)
    # A single title row (bare object, not a list) still normalizes to a tuple.
    assert book.title_rows == ({"id": 1, "tit": "heading", "lvl": 1, "sub": 0},)


def test_read_all_parses_a_failed_result_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A per-file failure (missing/corrupt file) is reported, not raised."""
    results = [
        {
            "Path": r"F:\shamela\Books\0\missing.mdb",
            "Succeeded": False,
            "Error": "Could not find file.",
            "BookRows": None,
            "TitleRows": None,
        }
    ]
    monkeypatch.setattr(subprocess, "run", _fake_run_writing_results(results))
    reader = PowerShellShamelaReader()

    parsed = reader.read_all((Path(r"F:\shamela\Books\0\missing.mdb"),))

    assert len(parsed) == 1
    assert parsed[0].succeeded is False
    assert parsed[0].error == "Could not find file."
    assert parsed[0].book_rows == ()
    assert parsed[0].title_rows == ()


def test_read_all_parses_multiple_ndjson_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    """Several files in one batch parse as separate NDJSON lines, in order."""
    results = [
        {
            "Path": r"F:\shamela\Books\0\1.mdb", "Succeeded": True, "Error": None,
            "BookRows": [{"id": 1, "nass": "one", "page": 1, "part": 1}], "TitleRows": [],
        },
        {
            "Path": r"F:\shamela\Books\0\2.mdb", "Succeeded": True, "Error": None,
            "BookRows": [{"id": 1, "nass": "two", "page": 1, "part": 1}], "TitleRows": [],
        },
    ]
    monkeypatch.setattr(subprocess, "run", _fake_run_writing_results(results))
    reader = PowerShellShamelaReader()

    parsed = reader.read_all(
        (Path(r"F:\shamela\Books\0\1.mdb"), Path(r"F:\shamela\Books\0\2.mdb"))
    )

    assert [book.book_rows[0]["nass"] for book in parsed] == ["one", "two"]


def test_read_all_raises_cleanly_when_the_results_file_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real bug found and fixed: a large batch could make PowerShell's
    ConvertTo-Json throw OutOfMemoryException while still exiting 0, so the
    results file ends up empty - this must raise a clear ShamelaReaderError,
    not an unhandled JSONDecodeError that kills the whole import run."""

    def _run(args, **kwargs):
        results_file = Path(args[args.index("-ResultsFile") + 1])
        results_file.write_text("", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", _run)
    reader = PowerShellShamelaReader()

    with pytest.raises(ShamelaReaderError):
        reader.read_all((Path(r"F:\shamela\Books\0\1.mdb"),))


def test_read_all_raises_when_the_script_itself_fails_to_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch-level failure (script crash, PowerShell missing) raises clearly."""

    def _raise(*args, **kwargs):
        raise subprocess.SubprocessError("boom")

    monkeypatch.setattr(subprocess, "run", _raise)
    reader = PowerShellShamelaReader()

    with pytest.raises(ShamelaReaderError):
        reader.read_all((Path(r"F:\shamela\Books\0\1.mdb"),))
