"""Tests for Master Library Storage Size Report Generator."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import openpyxl
import pytest

from islamic_research_hub.interfaces.library_size_report_generator_cli import generate_library_size_reports


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
            INSERT INTO Books VALUES (101, 1, 'Sahih Bukhari', 'Bukhari', 'Dar', 'ur', 'Hadith', 1500);
            """
        )


def test_generate_library_size_reports(tmp_path: Path) -> None:
    db_path = tmp_path / "books.db"
    _seed_test_db(db_path)
    md_p = tmp_path / "size_report.md"
    js_p = tmp_path / "size_report.json"
    ex_p = tmp_path / "size_report.xlsx"
    cs_p = tmp_path / "size_report.csv"

    gb, tb, pgs = generate_library_size_reports(db_path, md_p, js_p, ex_p, cs_p)
    assert tb == 1
    assert pgs == 1500

    assert md_p.is_file()
    assert js_p.is_file()
    assert ex_p.is_file()
    assert cs_p.is_file()

    with open(js_p, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["master_storage_summary"]["total_books"] == 1
