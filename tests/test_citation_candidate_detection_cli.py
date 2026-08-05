"""Tests for the citation candidate detection CLI."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
from islamic_research_hub.interfaces.citation_candidate_detection_cli import build_parser, run

_DISTINCTIVE_TITLE = "A Real Distinctive Citation Target Title"


def _build_args(database_path: Path, sample: int | None = None):
    arguments = ["--database", str(database_path)]
    if sample is not None:
        arguments += ["--sample", str(sample)]
    return build_parser().parse_args(arguments)


def _seed_real_citation(database_path: Path) -> None:
    MasterBookRepository().import_books(
        database_path,
        (
            Book(
                information={"Name": _DISTINCTIVE_TITLE},
                categories=(),
                table_of_contents=(),
                pages=(Page(1, 1, "front matter", None),),
            ),
            Book(
                information={"Name": "A Citing Book"},
                categories=(),
                table_of_contents=(),
                pages=(Page(1, 1, f"as mentioned in {_DISTINCTIVE_TITLE} earlier", None),),
            ),
        ),
        (database_path.parent / "a.mjbz", database_path.parent / "b.mjbz"),
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)


def test_missing_database_returns_error_without_crashing(tmp_path: Path) -> None:
    args = _build_args(tmp_path / "does_not_exist.db")

    exit_code = run(args)

    assert exit_code == 1


def test_full_run_detects_and_stores_real_candidates(tmp_path: Path, capsys) -> None:
    database_path = tmp_path / "books.db"
    _seed_real_citation(database_path)

    exit_code = run(_build_args(database_path))

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "1 candidate(s) found" in output
    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM CitationCandidates").fetchone()[0]
    assert count == 1


def test_sample_run_measures_timing_without_writing_anything(tmp_path: Path, capsys) -> None:
    database_path = tmp_path / "books.db"
    _seed_real_citation(database_path)

    exit_code = run(_build_args(database_path, sample=1))

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "estimated full run" in output
    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM CitationCandidates").fetchone()[0]
    assert count == 0  # --sample never writes


def test_sample_run_on_unmigrated_database_reports_no_anchors(tmp_path: Path, capsys) -> None:
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (
            Book(
                information={"Name": _DISTINCTIVE_TITLE},
                categories=(),
                table_of_contents=(),
                pages=(Page(1, 1, "front matter", None),),
            ),
        ),
        (database_path.parent / "a.mjbz",),
    )

    exit_code = run(_build_args(database_path, sample=1))

    assert exit_code == 0
    assert "No anchors found" in capsys.readouterr().out
