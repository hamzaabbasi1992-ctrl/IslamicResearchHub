"""End-to-end tests for the title cleanup command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.interfaces.title_cleanup_cli import main


def test_main_cleans_titles_in_the_named_library_only(tmp_path: Path, capsys) -> None:
    """Only books in the requested library get cleaned; others are untouched."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (Book(information={"Name": "ALL_CAPS_TITLE"}, categories=(), table_of_contents=(), pages=()),),
        (tmp_path / "a.mjbz",),
        library_name="Target Library",
    )
    repository.import_books(
        database_path,
        (Book(information={"Name": "OTHER_CAPS_TITLE"}, categories=(), table_of_contents=(), pages=()),),
        (tmp_path / "b.mjbz",),
        library_name="Other Library",
    )

    exit_code = main(
        [
            "--library", "Target Library",
            "--database", str(database_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Titles cleaned up: 1" in captured.out

    with sqlite3.connect(database_path) as connection:
        titles = {
            row[0]
            for row in connection.execute("SELECT Title FROM Books").fetchall()
        }
    assert "All Caps Title" in titles
    assert "OTHER_CAPS_TITLE" in titles
