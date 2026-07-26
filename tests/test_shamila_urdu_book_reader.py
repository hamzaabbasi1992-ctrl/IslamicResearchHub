"""Tests for reading Maktaba Shamila Urdu's per-book SQLite format."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.infrastructure.persistence.shamila_urdu_book_reader import (
    ShamilaUrduBookReadError,
    ShamilaUrduBookReader,
)


def _make_book_db(
    path: Path,
    metadata: dict[str, str],
    pages: list[tuple[int, str, str | None]],
    toc: list[tuple[int, int, str]],
) -> None:
    """Create a real, minimal Shamila Urdu book database for testing."""
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE Book (ID INTEGER PRIMARY KEY, txt TEXT, fnotes TEXT)")
        connection.execute(
            "CREATE TABLE tableOfContents (ID INTEGER, pageID INTEGER, txt TEXT, headingType TEXT)"
        )
        connection.execute("CREATE TABLE metadata (fieldName TEXT, fieldValue TEXT)")
        connection.executemany(
            "INSERT INTO Book (ID, txt, fnotes) VALUES (?, ?, ?)", pages
        )
        connection.executemany(
            "INSERT INTO tableOfContents (ID, pageID, txt, headingType) VALUES (?, ?, ?, 'h1')",
            toc,
        )
        connection.executemany(
            "INSERT INTO metadata (fieldName, fieldValue) VALUES (?, ?)",
            list(metadata.items()),
        )


def test_reads_real_book_with_html_stripped(tmp_path: Path) -> None:
    """A book's HTML-styled content is stripped to plain text."""
    db_path = tmp_path / "sample.db"
    _make_book_db(
        db_path,
        metadata={
            "Book Name": "احکام و مسائل",
            "Writer": "حافظ عبد المنان",
            "Publisher": "المکتبہ الکریمیہ",
        },
        pages=[
            (1, '<span class="mu mb1 ms22"> مقدمہ</span>\n<span class="ms14">متن</span>', None),
        ],
        toc=[],
    )

    book = ShamilaUrduBookReader().read(db_path, category_name="ahkaam")

    assert book.information["Name"] == "احکام و مسائل"
    assert book.information["ANAME"] == "حافظ عبد المنان"
    assert book.information["PNAME"] == "المکتبہ الکریمیہ"
    assert book.information["Language"] == "Urdu"
    assert book.information["MJCN"] == "ahkaam"
    assert book.information["MJBN"] == "sample"
    assert len(book.pages) == 1
    assert "<span" not in book.pages[0].content_f
    assert "مقدمہ" in book.pages[0].content_f
    assert "متن" in book.pages[0].content_f


def test_reads_footnotes_when_present(tmp_path: Path) -> None:
    """Real footnote text is extracted and HTML-stripped like page content."""
    db_path = tmp_path / "sample.db"
    _make_book_db(
        db_path,
        metadata={"Book Name": "Test"},
        pages=[
            (1, "<span>page one</span>", "<span>[1] a real footnote</span>"),
            (2, "<span>page two</span>", None),
            (3, "<span>page three</span>", "   "),
        ],
        toc=[],
    )

    book = ShamilaUrduBookReader().read(db_path)

    assert book.pages[0].footnote == "[1] a real footnote"
    assert book.pages[1].footnote is None
    assert book.pages[2].footnote is None


def test_falls_back_to_translator_when_no_writer(tmp_path: Path) -> None:
    """A translation with no listed author uses the translator instead."""
    db_path = tmp_path / "sample.db"
    _make_book_db(
        db_path,
        metadata={"Book Name": "ترجمہ", "Translator": "مولانا جوناگڑھی"},
        pages=[(1, "<span>text</span>", None)],
        toc=[],
    )

    book = ShamilaUrduBookReader().read(db_path)

    assert book.information["ANAME"] == "مولانا جوناگڑھی"


def test_table_of_contents_skips_blank_entries(tmp_path: Path) -> None:
    """Empty-title TOC rows (a real pattern in the source data) are skipped."""
    db_path = tmp_path / "sample.db"
    _make_book_db(
        db_path,
        metadata={"Book Name": "Test"},
        pages=[(1, "<span>text</span>", None)],
        toc=[(1, 1, "کتاب العقائد"), (2, 1, ""), (3, 1, "   ")],
    )

    book = ShamilaUrduBookReader().read(db_path)

    assert len(book.table_of_contents) == 1
    assert book.table_of_contents[0].title == "کتاب العقائد"


def test_raises_clear_error_for_corrupted_database(tmp_path: Path) -> None:
    """A corrupted/invalid database raises a clear error, not a raw crash."""
    db_path = tmp_path / "corrupted.db"
    db_path.write_bytes(b"not a real sqlite file")

    with pytest.raises(ShamilaUrduBookReadError):
        ShamilaUrduBookReader().read(db_path)
