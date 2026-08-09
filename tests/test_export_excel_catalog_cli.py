"""Tests for Excel and CSV catalog exporter."""

import sqlite3
from contextlib import closing
from pathlib import Path

import openpyxl
import pytest

from islamic_research_hub.interfaces.export_excel_catalog_cli import export_books_to_excel_and_csv


def _seed_test_db(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE Libraries (
                LibraryID INTEGER PRIMARY KEY,
                Name TEXT NOT NULL
            );
            CREATE TABLE Books (
                BookID INTEGER PRIMARY KEY,
                LibraryID INTEGER,
                Title TEXT NOT NULL,
                Author TEXT,
                Publisher TEXT,
                Language TEXT,
                Category TEXT,
                PageCount INTEGER
            );
            INSERT INTO Libraries VALUES (1, 'Main Library');
            INSERT INTO Books VALUES (101, 1, 'Zahr al-Ruba', 'Imam Suyuti', 'Dar', 'Arabic', 'Hadith', 150);
            INSERT INTO Books VALUES (102, 1, 'Al-Bidayah wa al-Nihayah', 'Ibn Kathir', 'Dar', 'Arabic', 'History', 500);
            """
        )


def test_export_books_to_excel_and_csv(tmp_path: Path) -> None:
    db_path = tmp_path / "books.db"
    _seed_test_db(db_path)
    excel_out = tmp_path / "catalog.xlsx"
    csv_out = tmp_path / "catalog.csv"

    count, ex_path, cs_path = export_books_to_excel_and_csv(db_path, excel_out, csv_out)
    assert count == 2
    assert ex_path.is_file()
    assert cs_path.is_file()

    wb = openpyxl.load_workbook(ex_path)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    headers = list(rows[0])
    assert headers == ["ID", "Title", "Author", "Maktaba", "Type / Category", "Pages Count"]

    # Check A-Z alphabetical ordering (Al-Bidayah before Zahr)
    first_title = rows[1][1]
    assert "Al-Bidayah" in first_title
