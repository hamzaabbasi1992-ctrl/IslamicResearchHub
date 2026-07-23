"""End-to-end tests for the PDF metadata catalog command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.interfaces.pdf_metadata_import_cli import main


def test_main_catalogs_pdfs_with_no_page_content(tmp_path: Path, capsys) -> None:
    """Every PDF becomes a title-only Book entry with zero pages."""
    folder = tmp_path / "pdfs"
    folder.mkdir()
    (folder / "Some Book.pdf").write_bytes(b"%PDF-1.4 fake content")

    database_path = tmp_path / "books.db"
    exit_code = main(
        [str(folder), "--library", "Test PDF Archive", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "PDF files found: 1" in captured.out
    assert "Books imported: 1" in captured.out

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT b.Title, b.PageCount FROM Books b "
            "JOIN Libraries l ON l.LibraryID = b.LibraryID WHERE l.Name = 'Test PDF Archive'"
        ).fetchone()
    assert row == ("Some Book", 0)
