"""Tests for English Islamic Library Ingestion Engine."""

import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.interfaces.import_english_books_cli import ensure_english_library_exists, ENGLISH_CORE_BOOKS_PRESETS


def test_ensure_english_library_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "books.db"
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("CREATE TABLE Libraries (LibraryID INTEGER PRIMARY KEY, Name TEXT NOT NULL);")
        lib_id = ensure_english_library_exists(conn)
        assert lib_id > 0

        # Run again to ensure idempotent lookup
        lib_id_2 = ensure_english_library_exists(conn)
        assert lib_id_2 == lib_id


def test_english_core_presets() -> None:
    assert len(ENGLISH_CORE_BOOKS_PRESETS) >= 10
    titles = [b["Title"] for b in ENGLISH_CORE_BOOKS_PRESETS]
    assert "Sahih al-Bukhari (English Translation)" in titles
    assert "Tafsir Ibn Kathir (English Abridged - 10 Volumes)" in titles
