"""Read-only SQLite adapter for the Maktaba Shamila Urdu `Quran/` collection.

The folder holds three kinds of self-contained `.db` file, each with its own
ayah-level content table - a different schema from both the `Books/` folder
and the `Hadith/` folder, discovered when the original Shamila Urdu import
silently failed to read this folder at all (see the CHANGELOG correction
note):

- `Quran.db`: the base Arabic text itself, in a `Quran` table.
- `Tarjuma*.db`: one Urdu translation, in a `Tarjuma` table.
- `Tafseer*.db`: one Urdu tafsir/commentary, in a `Tafseer` table.

Every variant is ayah-by-ayah with a surah number and title, so one reader
handles all three: one ayah row becomes one `Page`, and surahs become the
table of contents.

`Quran.db`'s own `metadata` table is vendor placeholder junk ("dsddd" /
"AAAA") rather than real data - the only case in this corpus where a
source's stated title/author is known-garbage rather than merely absent, so
it is deliberately overridden with an honest, factual label instead of
propagated.
"""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Chapter, Page
from islamic_research_hub.shared.html_text_extraction import strip_html_to_text

LOGGER = logging.getLogger(__name__)

_BASE_TEXT_TABLE = "Quran"
_TRANSLATION_TABLE = "Tarjuma"
_COMMENTARY_TABLE = "Tafseer"
_CONTENT_TABLES = (_BASE_TEXT_TABLE, _TRANSLATION_TABLE, _COMMENTARY_TABLE)

BASE_TEXT_FILE_NAME = "Quran.db"
_BASE_TEXT_TITLE = "القرآن الکریم (عربی متن)"


class ShamilaUrduQuranReadError(Exception):
    """Raised when a Shamila Urdu Quran-folder database cannot be read."""


class ShamilaUrduQuranReader:
    """Extract one Quran text/translation/tafsir from its self-contained `.db` file."""

    def read(self, database_path: Path, category_name: str | None = "Quran") -> Book:
        """Read metadata and every ayah, grouped into a per-surah table of contents."""
        try:
            with closing(self._connect_read_only(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                metadata = self._read_metadata(connection)
                table_name = self._find_content_table(connection)
                rows = connection.execute(
                    f"SELECT * FROM {table_name} ORDER BY ID"
                ).fetchall()
        except sqlite3.Error as error:
            LOGGER.exception("Unable to read Shamila Urdu Quran-folder file: %s", database_path)
            raise ShamilaUrduQuranReadError(
                "The Shamila Urdu Quran-folder database could not be read."
            ) from error

        is_html_styled = table_name in (_TRANSLATION_TABLE, _COMMENTARY_TABLE)
        pages = tuple(
            _build_page(index, row, strip_html=is_html_styled)
            for index, row in enumerate(rows, start=1)
        )
        chapters = _build_chapters(rows)

        if database_path.name == BASE_TEXT_FILE_NAME:
            name, author = _BASE_TEXT_TITLE, None
        else:
            name, author = metadata.get("Book Name"), (
                metadata.get("Writer") or metadata.get("Translator")
            )

        information = {
            "MJBN": database_path.stem,
            "Name": name,
            "ANAME": author,
            "PNAME": metadata.get("Publisher") if database_path.name != BASE_TEXT_FILE_NAME else None,
            "Language": "Urdu",
            "MJCN": category_name,
        }
        return Book(
            information=information,
            categories=(),
            table_of_contents=chapters,
            pages=pages,
        )

    @staticmethod
    def _connect_read_only(database_path: Path) -> sqlite3.Connection:
        """Open the existing database without write access."""
        return sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)

    @staticmethod
    def _read_metadata(connection: sqlite3.Connection) -> dict[str, str]:
        """Read the file's own key/value metadata table."""
        rows = connection.execute("SELECT fieldName, fieldValue FROM metadata").fetchall()
        return {row["fieldName"]: row["fieldValue"] for row in rows if row["fieldValue"]}

    @staticmethod
    def _find_content_table(connection: sqlite3.Connection) -> str:
        """Return whichever of Quran/Tarjuma/Tafseer this file actually has."""
        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for candidate in _CONTENT_TABLES:
            if candidate in table_names:
                return candidate
        raise ShamilaUrduQuranReadError(
            f"No recognized content table found (expected one of {_CONTENT_TABLES})."
        )


def _build_page(page_number: int, row: sqlite3.Row, *, strip_html: bool) -> Page:
    """Turn one ayah row into a page, stripping HTML only where it is actually used."""
    text = row["txt"]
    content = strip_html_to_text(text) if strip_html else (text.strip() if text else None)
    return Page(
        content_id=page_number,
        page_number=page_number,
        content_f=content,
        content_p=None,
        footnote=None,
    )


def _build_chapters(rows: tuple[sqlite3.Row, ...]) -> tuple[Chapter, ...]:
    """Group ayah rows into one chapter per surah."""
    chapters: list[Chapter] = []
    current_surah_number: object = None

    for page_number, row in enumerate(rows, start=1):
        surah_number = row["SurahNumber"]
        if surah_number != current_surah_number:
            title = (row["surahTitle"] or "").strip() or f"Surah {surah_number}"
            chapters.append(
                Chapter(
                    title_id=surah_number,
                    title=title,
                    page_number=page_number,
                    parent_id=None,
                    sort_key=surah_number,
                )
            )
            current_surah_number = surah_number

    return tuple(chapters)
