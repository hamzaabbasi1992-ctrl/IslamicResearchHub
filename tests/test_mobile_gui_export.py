"""Tests for direct desktop GUI mobile export functionality."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from islamic_research_hub.interfaces.book_package_export_cli import export_book_package_to_file
from islamic_research_hub.interfaces.catalog_export_cli import export_catalog_to_file
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.import_screen import ImportScreen
from islamic_research_hub.interfaces.desktop_app.viewer_screen import ViewerScreen


def _seed_test_database(db_path: Path) -> None:
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
            CREATE TABLE Pages (
                PageID INTEGER PRIMARY KEY,
                BookID INTEGER,
                PageNo INTEGER,
                Content TEXT,
                HadeesNumber INTEGER,
                AyahNumber INTEGER
            );
            CREATE TABLE Chapters (
                ChapterID INTEGER PRIMARY KEY,
                BookID INTEGER,
                ParentChapterID INTEGER,
                Title TEXT,
                PageNo INTEGER,
                SortKey INTEGER
            );

            INSERT INTO Libraries VALUES (1, 'Main Library');
            INSERT INTO Books VALUES (101, 1, 'Sahih Bukhari', 'Imam Bukhari', 'Darussalam', 'Arabic', 'Hadith', 10, 2, 256, NULL, 1);
            INSERT INTO Pages VALUES (1, 101, 1, 'Innamal amalu bin niyyat', 1, NULL);
            INSERT INTO Chapters VALUES (1, 101, NULL, 'Book of Revelation', 1, 1);
            """
        )


def test_export_catalog_to_file(tmp_path: Path) -> None:
    db_path = tmp_path / "books.db"
    _seed_test_database(db_path)
    output_catalog = tmp_path / "catalog.db"

    num_libs, num_books, size_mb = export_catalog_to_file(db_path, output_catalog)
    assert num_libs == 1
    assert num_books == 1
    assert output_catalog.is_file()
    assert size_mb > 0


def test_export_book_package_to_file(tmp_path: Path) -> None:
    db_path = tmp_path / "books.db"
    _seed_test_database(db_path)
    output_book = tmp_path / "book_101.db"

    title, pages, chapters, size_mb = export_book_package_to_file(db_path, 101, output_book)
    assert title == "Sahih Bukhari"
    assert pages == 1
    assert chapters == 1
    assert output_book.is_file()
    assert size_mb > 0


def test_export_category_books_to_folder(tmp_path: Path) -> None:
    from islamic_research_hub.interfaces.book_package_export_cli import (
        export_category_books_to_folder,
    )

    db_path = tmp_path / "books.db"
    _seed_test_database(db_path)
    output_dir = tmp_path / "export_out"

    count, size_mb = export_category_books_to_folder(db_path, "Hadith", output_dir)
    assert count == 1
    assert (output_dir / "book_101.db").is_file()
    assert size_mb > 0


def test_import_screen_has_export_catalog_and_batch_buttons(qtbot, tmp_path: Path) -> None:
    db_path = tmp_path / "books.db"
    _seed_test_database(db_path)
    translator = Translator()

    screen = ImportScreen(db_path, translator)
    qtbot.addWidget(screen)

    assert hasattr(screen, "_export_catalog_button")
    assert screen._export_catalog_button.text() == "📱 Export Mobile Catalog (.db)"
    assert hasattr(screen, "_batch_export_button")
    assert screen._batch_export_button.text() == "📦 Batch Export Books..."


def test_viewer_screen_has_export_mobile_button(qtbot, tmp_path: Path) -> None:
    db_path = tmp_path / "books.db"
    _seed_test_database(db_path)
    translator = Translator()

    viewer = ViewerScreen(db_path, translator)
    qtbot.addWidget(viewer)

    assert hasattr(viewer, "_export_mobile_button")
    assert viewer._export_mobile_button.text() == "📱 Export for Mobile..."
