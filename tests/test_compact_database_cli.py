"""Tests for Database Compactor & Space Reclaimer CLI."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from islamic_research_hub.interfaces.compact_database_cli import compact_and_reclaim_space


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
                ChapterCount INTEGER,
                PublishYear INTEGER,
                SeriesID INTEGER,
                VolumeNumber INTEGER
            );
            CREATE TABLE Chapters (
                ChapterID INTEGER PRIMARY KEY,
                BookID INTEGER,
                ParentChapterID INTEGER,
                Title TEXT,
                PageNo INTEGER,
                SortKey INTEGER
            );
            CREATE TABLE Pages (
                PageID INTEGER PRIMARY KEY,
                BookID INTEGER,
                PageNo INTEGER,
                Content TEXT,
                HadeesNumber INTEGER,
                AyahNumber INTEGER
            );
            INSERT INTO Libraries VALUES (1, 'Main Library');
            INSERT INTO Books VALUES (101, 1, 'Sahih Bukhari', 'Bukhari', 'Dar', 'ur', 'Hadith', 1, 1, 256, NULL, 1);
            INSERT INTO Pages VALUES (1, 101, 1, 'Innamal amalu bin niyyat', 1, NULL);
            """
        )


def test_compact_and_reclaim_space(tmp_path: Path) -> None:
    src_db = tmp_path / "books.db"
    dst_db = tmp_path / "books_compact.db"
    _seed_test_db(src_db)

    start_gb, final_gb, saved_gb = compact_and_reclaim_space(src_db, dst_db)
    assert dst_db.is_file()
    assert final_gb > 0

    with closing(sqlite3.connect(dst_db)) as conn:
        conn.row_factory = sqlite3.Row
        b = conn.execute("SELECT * FROM Books WHERE BookID = 101").fetchone()
        assert b["Title"] == "Sahih Bukhari"
        p = conn.execute("SELECT * FROM Pages WHERE PageID = 1").fetchone()
        assert "Innamal amalu" in p["Content"]
