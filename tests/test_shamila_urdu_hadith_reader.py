"""Tests for reading Maktaba Shamila Urdu's `Hadith/` collection format."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.infrastructure.persistence.shamila_urdu_hadith_reader import (
    ShamilaUrduHadithReadError,
    ShamilaUrduHadithReader,
)

_HADITH_COLUMNS = (
    "ID", "BookId", "BookNameArabic", "BookNameUrdu", "KitabID", "KitabHiddenID",
    "KitaabNameArabic", "KitaabNameUrdu", "BaabID", "BaabHiddenID",
    "BaabNameArabic", "BaabNameUrdu", "HadeesNumber", "HadithArabicText",
    "HadithArabicTextSearch", "HadithUrduText", "HadithHashiaText",
    "HadithTypeAtraaf", "HadithTypeRawaat", "HadithTypeQFT",
    "HadithHukamAjmali", "HadithHukamTafseeli", "HadithMouzuhArabic",
    "HadithMouzuhUrdu", "HadithHukamTafseeliArabic", "HadithTakhreej",
)


def _row(
    row_id: int,
    kitab_id: int,
    kitab_name: str,
    baab_id: int,
    baab_name: str,
    arabic: str,
    urdu: str,
    hashia: str | None = None,
    grade: str | None = None,
) -> tuple:
    values = {
        "ID": row_id,
        "BookId": "1",
        "BookNameArabic": "Test",
        "BookNameUrdu": "ٹیسٹ",
        "KitabID": kitab_id,
        "KitabHiddenID": str(kitab_id),
        "KitaabNameArabic": kitab_name,
        "KitaabNameUrdu": kitab_name,
        "BaabID": baab_id,
        "BaabHiddenID": str(baab_id),
        "BaabNameArabic": baab_name,
        "BaabNameUrdu": baab_name,
        "HadeesNumber": row_id,
        "HadithArabicText": arabic,
        "HadithArabicTextSearch": arabic,
        "HadithUrduText": urdu,
        "HadithHashiaText": hashia,
        "HadithTypeAtraaf": "",
        "HadithTypeRawaat": "",
        "HadithTypeQFT": "",
        "HadithHukamAjmali": grade,
        "HadithHukamTafseeli": "",
        "HadithMouzuhArabic": "",
        "HadithMouzuhUrdu": "",
        "HadithHukamTafseeliArabic": "",
        "HadithTakhreej": "",
    }
    return tuple(values[column] for column in _HADITH_COLUMNS)


def _make_hadith_db(
    path: Path,
    metadata: dict[str, str],
    rows: list[tuple],
    supplementary_rows: list[tuple] | None = None,
) -> None:
    """Create a real, minimal Shamila Urdu hadith-collection database for testing."""
    columns_sql = ", ".join(f"{name} TEXT" for name in _HADITH_COLUMNS if name != "ID")
    with sqlite3.connect(path) as connection:
        connection.execute(f"CREATE TABLE hadith (ID INTEGER PRIMARY KEY, {columns_sql})")
        connection.execute("CREATE TABLE metadata (fieldName TEXT, fieldValue TEXT)")
        placeholders = ", ".join("?" for _ in _HADITH_COLUMNS)
        connection.executemany(
            f"INSERT INTO hadith ({', '.join(_HADITH_COLUMNS)}) VALUES ({placeholders})", rows
        )
        connection.executemany(
            "INSERT INTO metadata (fieldName, fieldValue) VALUES (?, ?)",
            list(metadata.items()),
        )
        if supplementary_rows is not None:
            connection.execute(f"CREATE TABLE hadith5 (ID INTEGER PRIMARY KEY, {columns_sql})")
            connection.executemany(
                f"INSERT INTO hadith5 ({', '.join(_HADITH_COLUMNS)}) VALUES ({placeholders})",
                supplementary_rows,
            )


def test_reads_real_hadith_collection_with_kitab_baab_hierarchy(tmp_path: Path) -> None:
    """A hadith collection is read as a book with Kitab -> Baab chapters."""
    db_path = tmp_path / "bukhari.db"
    _make_hadith_db(
        db_path,
        metadata={"Book Name": "صحیح البخاری", "Writer": "امام بخاری"},
        rows=[
            _row(1, 1, "کتاب الایمان", 1, "باب اول", "نص عربی اول", "پہلی حدیث", grade="صحیح"),
            _row(2, 1, "کتاب الایمان", 1, "باب اول", "نص عربی دوم", "دوسری حدیث"),
            _row(3, 1, "کتاب الایمان", 2, "باب دوم", "نص عربی سوم", "تیسری حدیث"),
            _row(4, 2, "کتاب الطہارۃ", 3, "باب اول", "نص عربی چہارم", "چوتھی حدیث"),
        ],
    )

    book = ShamilaUrduHadithReader().read(db_path, category_name="Hadith")

    assert book.information["Name"] == "صحیح البخاری"
    assert book.information["ANAME"] == "امام بخاری"
    assert book.information["Language"] == "Urdu"
    assert book.information["MJCN"] == "Hadith"
    assert len(book.pages) == 4
    assert "نص عربی اول" in book.pages[0].content_f
    assert "پہلی حدیث" in book.pages[0].content_f
    assert "[صحیح]" in book.pages[0].content_f

    assert len(book.table_of_contents) == 2
    first_kitab, second_kitab = book.table_of_contents
    assert first_kitab.title == "کتاب الایمان"
    assert first_kitab.page_number == 1
    assert len(first_kitab.children) == 2
    assert first_kitab.children[0].title == "باب اول"
    assert first_kitab.children[0].parent_id == first_kitab.title_id
    assert first_kitab.children[1].title == "باب دوم"
    assert first_kitab.children[1].page_number == 3
    assert second_kitab.title == "کتاب الطہارۃ"
    assert second_kitab.page_number == 4


def test_hadees_number_is_captured_not_dropped(tmp_path: Path) -> None:
    """The real hadith number (previously silently dropped) is captured on each page."""
    db_path = tmp_path / "bukhari.db"
    _make_hadith_db(
        db_path,
        metadata={"Book Name": "صحیح البخاری"},
        rows=[
            _row(1, 1, "کتاب الایمان", 1, "باب اول", "نص عربی اول", "پہلی حدیث"),
            _row(2, 1, "کتاب الایمان", 1, "باب اول", "نص عربی دوم", "دوسری حدیث"),
        ],
    )

    book = ShamilaUrduHadithReader().read(db_path)

    assert book.pages[0].hadees_number == "1"
    assert book.pages[1].hadees_number == "2"


def test_commentary_becomes_the_footnote_with_html_stripped(tmp_path: Path) -> None:
    """HadithHashiaText (real commentary) is stripped of HTML and stored as the footnote."""
    db_path = tmp_path / "abu-dawood.db"
    _make_hadith_db(
        db_path,
        metadata={"Book Name": "Test"},
        rows=[
            _row(
                1, 1, "کتاب", 1, "باب", "عربی", "اردو",
                hashia="<span>تشریح: <br>یہ ایک حقیقی تشریح ہے</span>",
            ),
            _row(2, 1, "کتاب", 1, "باب", "عربی دو", "اردو دو", hashia=None),
        ],
    )

    book = ShamilaUrduHadithReader().read(db_path)

    assert book.pages[0].footnote == "تشریح:\nیہ ایک حقیقی تشریح ہے"
    assert book.pages[1].footnote is None


def test_supplementary_hadith5_table_is_appended_not_dropped(tmp_path: Path) -> None:
    """tirmizi.db's real-world extra `hadith5` table is included, not silently lost."""
    db_path = tmp_path / "tirmizi.db"
    _make_hadith_db(
        db_path,
        metadata={"Book Name": "جامع الترمذی"},
        rows=[_row(1, 1, "کتاب اول", 1, "باب اول", "عربی اول", "اردو اول")],
        supplementary_rows=[_row(389, 4, "کتاب دوم", 2, "باب دوم", "عربی ضمیمہ", "اردو ضمیمہ")],
    )

    book = ShamilaUrduHadithReader().read(db_path)

    assert len(book.pages) == 2
    assert "اردو ضمیمہ" in book.pages[1].content_f
    assert len(book.table_of_contents) == 2
    assert book.table_of_contents[1].title == "کتاب دوم"
    assert book.table_of_contents[1].page_number == 2


def test_raises_clear_error_for_corrupted_database(tmp_path: Path) -> None:
    """A corrupted/invalid database raises a clear error, not a raw crash."""
    db_path = tmp_path / "corrupted.db"
    db_path.write_bytes(b"not a real sqlite file")

    with pytest.raises(ShamilaUrduHadithReadError):
        ShamilaUrduHadithReader().read(db_path)
