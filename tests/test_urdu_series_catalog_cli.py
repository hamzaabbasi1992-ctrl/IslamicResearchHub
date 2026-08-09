"""Tests for Urdu Multi-Volume Series Catalog Exporter."""

import sqlite3
from contextlib import closing
from pathlib import Path

import openpyxl
import pytest

from islamic_research_hub.interfaces.urdu_series_catalog_cli import generate_urdu_series_catalog, is_urdu_text, extract_volume_number


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
                PageCount INTEGER,
                VolumeNumber INTEGER
            );
            INSERT INTO Libraries VALUES (1, 'Maktaba Jibreel');
            INSERT INTO Books VALUES (101, 1, 'تفسیر عثمانی جلد 1', 'مفتی عثمانی', 'Dar', 'ur', 'Tafsir', 400, 1);
            INSERT INTO Books VALUES (102, 1, 'تفسیر عثمانی جلد 3', 'مفتی عثمانی', 'Dar', 'ur', 'Tafsir', 450, 3);
            """
        )


def test_is_urdu_text() -> None:
    assert is_urdu_text("تفسیر عثمانی جلد 1", "ur") is True
    assert is_urdu_text("Sahih Bukhari", "en") is False


def test_extract_volume_number() -> None:
    assert extract_volume_number("تفسیر عثمانی جلد 3", None) == 3
    assert extract_volume_number("معارف القرآن جلد نمبر 8", None) == 8


def test_generate_urdu_series_catalog(tmp_path: Path) -> None:
    db_path = tmp_path / "books.db"
    _seed_test_db(db_path)
    ex_path = tmp_path / "urdu_series.xlsx"
    cs_path = tmp_path / "urdu_series.csv"
    docs_ex = tmp_path / "docs_urdu.xlsx"
    docs_cs = tmp_path / "docs_urdu.csv"

    count, e_out, c_out = generate_urdu_series_catalog(db_path, ex_path, cs_path, docs_ex, docs_cs)
    assert count == 1
    assert e_out.is_file()
    assert c_out.is_file()

    wb = openpyxl.load_workbook(e_out)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    headers = list(rows[0])
    assert "Series Title" in headers
    assert "True Total Volumes (Internet Reference)" in headers
    assert "Missing / Remaining Volumes List" in headers

    row1 = list(rows[1])
    assert "تفسیر عثمانی" in row1[1]
    assert row1[6] == 3  # Tafsir Usmani true total is 3 volumes
    assert "2" in str(row1[7])  # Volume 2 is missing
