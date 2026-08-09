"""Tests for Urdu Khutbat & Bayanat Catalog Exporter."""

import sqlite3
from contextlib import closing
from pathlib import Path

import openpyxl
import pytest

from islamic_research_hub.interfaces.khutbat_bayanat_catalog_cli import generate_khutbat_bayanat_catalog, clean_khutbat_title, extract_volume_number


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
            INSERT INTO Books VALUES (101, 1, 'اصلاحی خطبات جلد 1', 'مفتی تقی عثمانی', 'Dar', 'ur', 'Khutbat', 400, 1);
            INSERT INTO Books VALUES (102, 1, 'اصلاحی خطبات جلد 2', 'مفتی تقی عثمانی', 'Dar', 'ur', 'Khutbat', 450, 2);
            """
        )


def test_clean_khutbat_title() -> None:
    assert clean_khutbat_title("اصلاحی خطبات جلد 1") == "اصلاحی خطبات"
    assert clean_khutbat_title("خطبات فقیر جلد 5") == "خطبات فقیر"


def test_extract_volume_number() -> None:
    assert extract_volume_number("اصلاحی خطبات جلد 18", None) == 18


def test_generate_khutbat_bayanat_catalog(tmp_path: Path) -> None:
    db_path = tmp_path / "books.db"
    _seed_test_db(db_path)
    ex_path = tmp_path / "khutbat.xlsx"
    cs_path = tmp_path / "khutbat.csv"
    docs_ex = tmp_path / "docs_khutbat.xlsx"
    docs_cs = tmp_path / "docs_khutbat.csv"

    total, present, missing, e_out, c_out = generate_khutbat_bayanat_catalog(db_path, ex_path, cs_path, docs_ex, docs_cs)
    assert total >= 1
    assert present == 1
    assert e_out.is_file()
    assert c_out.is_file()

    wb = openpyxl.load_workbook(e_out)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    headers = list(rows[0])
    assert "Khutbat & Bayanat Series Title" in headers
    assert "True Total Volumes (Internet Reference)" in headers

    row1 = list(rows[1])
    assert "اصلاحی خطبات" in row1[1]
    assert row1[6] == 20  # Islahi Khutbat published total is 20 volumes
