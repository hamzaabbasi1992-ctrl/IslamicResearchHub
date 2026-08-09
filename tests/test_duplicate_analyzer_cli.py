"""Tests for Duplicate Books Analyzer CLI."""

import sqlite3
from contextlib import closing
from pathlib import Path

import openpyxl
import pytest

from islamic_research_hub.interfaces.duplicate_analyzer_cli import analyze_duplicate_books, normalize_title_key


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
            INSERT INTO Libraries VALUES (1, 'Maktaba Shamela');
            INSERT INTO Libraries VALUES (2, 'Maktaba Jibreel');
            INSERT INTO Books VALUES (101, 1, 'Sahih Bukhari', 'Bukhari', 'Dar', 'Arabic', 'Hadith', 1500);
            INSERT INTO Books VALUES (102, 2, 'Sahih Bukhari (2)', 'Bukhari', 'Dar', 'Arabic', 'Hadith', 1500);
            INSERT INTO Books VALUES (103, 1, 'Unique Book Title', 'Author X', 'Dar', 'Arabic', 'Fiqh', 200);
            """
        )


def test_normalize_title_key() -> None:
    assert normalize_title_key("Sahih Bukhari (2)") == "sahih bukhari"
    assert normalize_title_key("Tafsir Usmani جلد 2") == "tafsir usmani"


def test_analyze_duplicate_books(tmp_path: Path) -> None:
    db_path = tmp_path / "books.db"
    _seed_test_db(db_path)
    xlsx_out = tmp_path / "dup_report.xlsx"
    csv_out = tmp_path / "dup_report.csv"

    num_groups, num_books, x_p, c_p = analyze_duplicate_books(db_path, xlsx_out, csv_out)
    assert num_groups == 1
    assert num_books == 2
    assert x_p.is_file()
    assert c_p.is_file()
