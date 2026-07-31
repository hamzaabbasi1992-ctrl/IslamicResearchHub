"""Tests for reading Maktaba Shamila Urdu's `Quran/` collection format."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.infrastructure.persistence.shamila_urdu_quran_reader import (
    BASE_TEXT_FILE_NAME,
    ShamilaUrduQuranReadError,
    ShamilaUrduQuranReader,
)


def _make_base_text_db(path: Path, rows: list[tuple[int, int, int, str, str]]) -> None:
    """Create a real, minimal base-Quran-text database (the `Quran` table variant)."""
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE Quran (ID INTEGER PRIMARY KEY, ParaNumber INTEGER, "
            "SurahNumber INTEGER, AyahNumber INTEGER, txt TEXT, txtSearch TEXT, "
            "surahTitle TEXT)"
        )
        connection.execute("CREATE TABLE metadata (fieldName TEXT, fieldValue TEXT)")
        connection.executemany(
            "INSERT INTO Quran (ID, ParaNumber, SurahNumber, AyahNumber, txt, txtSearch, "
            "surahTitle) VALUES (?, 1, ?, ?, ?, ?, ?)",
            [(row_id, surah, ayah, text, text, title) for row_id, surah, ayah, text, title in rows],
        )
        connection.executemany(
            "INSERT INTO metadata (fieldName, fieldValue) VALUES (?, ?)",
            [("Book Name", "dsddd"), ("Writer", "AAAA")],
        )


def _make_tarjuma_or_tafseer_db(
    path: Path,
    table_name: str,
    metadata: dict[str, str],
    rows: list[tuple[int, str, int, str, int]],
) -> None:
    """Create a real, minimal Tarjuma/Tafseer database (the ayah-commentary variant)."""
    with sqlite3.connect(path) as connection:
        connection.execute(
            f"CREATE TABLE {table_name} (ID INTEGER PRIMARY KEY, txt TEXT, "
            "SurahNumber INTEGER, surahTitle TEXT, ayahNumber INTEGER)"
        )
        connection.execute("CREATE TABLE metadata (fieldName TEXT, fieldValue TEXT)")
        connection.executemany(
            f"INSERT INTO {table_name} (ID, txt, SurahNumber, surahTitle, ayahNumber) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        connection.executemany(
            "INSERT INTO metadata (fieldName, fieldValue) VALUES (?, ?)",
            list(metadata.items()),
        )


def test_base_text_uses_an_honest_title_not_the_placeholder_metadata(tmp_path: Path) -> None:
    """Quran.db's own metadata is vendor placeholder junk, so it's overridden, not trusted."""
    db_path = tmp_path / BASE_TEXT_FILE_NAME
    _make_base_text_db(
        db_path,
        rows=[
            (1, 1, 1, "بِسْمِ اللَّهِ", "الفاتحۃ"),
            (2, 1, 2, "الْحَمْدُ لِلَّهِ", "الفاتحۃ"),
            (3, 2, 1, "الم", "البقرۃ"),
        ],
    )

    book = ShamilaUrduQuranReader().read(db_path, category_name="Quran")

    assert book.information["Name"] != "dsddd"
    assert book.information["ANAME"] is None
    assert len(book.pages) == 3
    assert book.pages[0].content_f == "بِسْمِ اللَّهِ"
    assert len(book.table_of_contents) == 2
    assert book.table_of_contents[0].title == "الفاتحۃ"
    assert book.table_of_contents[0].page_number == 1
    assert book.table_of_contents[1].title == "البقرۃ"
    assert book.table_of_contents[1].page_number == 3


def test_ayah_number_is_captured_not_dropped(tmp_path: Path) -> None:
    """The real ayah number (previously silently dropped) is captured on each page."""
    db_path = tmp_path / BASE_TEXT_FILE_NAME
    _make_base_text_db(
        db_path,
        rows=[
            (1, 1, 1, "بِسْمِ اللَّهِ", "الفاتحۃ"),
            (2, 1, 2, "الْحَمْدُ لِلَّهِ", "الفاتحۃ"),
            (3, 2, 1, "الم", "البقرۃ"),
        ],
    )

    book = ShamilaUrduQuranReader().read(db_path)

    assert book.pages[0].ayah_number == "1"
    assert book.pages[1].ayah_number == "2"
    assert book.pages[2].ayah_number == "1"


def test_translation_strips_html_and_keeps_real_metadata(tmp_path: Path) -> None:
    """A Tarjuma file's HTML-styled verse text is stripped; its real title is kept."""
    db_path = tmp_path / "01_TarjumaJunagarhi.db"
    _make_tarjuma_or_tafseer_db(
        db_path,
        "Tarjuma",
        metadata={"Book Name": "ترجمہ جوناگڑھی", "Writer": "مولانا جوناگڑھی صاحب"},
        rows=[
            (1, '<span class="ms18">شروع اللہ کے نام سے</span>', 1, "الفاتحة", 1),
            (2, '<span class="ms18">ہر طرح کی تعریف</span>', 1, "الفاتحة", 2),
        ],
    )

    book = ShamilaUrduQuranReader().read(db_path, category_name="Quran")

    assert book.information["Name"] == "ترجمہ جوناگڑھی"
    assert book.information["ANAME"] == "مولانا جوناگڑھی صاحب"
    assert "<span" not in book.pages[0].content_f
    assert "شروع اللہ کے نام سے" in book.pages[0].content_f


def test_tafseer_table_is_recognized_like_tarjuma(tmp_path: Path) -> None:
    """A Tafseer file (commentary) uses the same ayah-level reading path as Tarjuma."""
    db_path = tmp_path / "08_TafseerIbnKathir.db"
    _make_tarjuma_or_tafseer_db(
        db_path,
        "Tafseer",
        metadata={"Book Name": "تفسیر ابن کثیر", "Writer": "ابن کثیر"},
        rows=[(1, "<p>تفسیر کا متن</p>", 1, "الفاتحة", 1)],
    )

    book = ShamilaUrduQuranReader().read(db_path)

    assert book.information["Name"] == "تفسیر ابن کثیر"
    assert "تفسیر کا متن" in book.pages[0].content_f


def test_raises_clear_error_for_corrupted_database(tmp_path: Path) -> None:
    """A corrupted/invalid database raises a clear error, not a raw crash."""
    db_path = tmp_path / "corrupted.db"
    db_path.write_bytes(b"not a real sqlite file")

    with pytest.raises(ShamilaUrduQuranReadError):
        ShamilaUrduQuranReader().read(db_path)
