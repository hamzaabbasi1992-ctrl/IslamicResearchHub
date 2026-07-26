"""Read-only SQLite adapter for the Maktaba Shamila Urdu `Hadith/` collection.

Each file is one self-contained hadith collection (e.g. `bukhari.db` = Sahih
al-Bukhari) with a `hadith` table - a different schema from the `Books/`
folder's `Book`/`tableOfContents` format, discovered when the original
Shamila Urdu import silently failed to read this folder at all (see the
CHANGELOG correction note). One `hadith` row becomes one `Page`: Arabic text
plus its Urdu translation as the searchable content, and the Urdu commentary
(`HadithHashiaText`, HTML-styled like `Books/`'s content) as the footnote.
Kitab/Baab headings become a two-level table of contents, exactly like a
real book's chapters/sub-chapters.

One source file (`tirmizi.db`) additionally carries a small `hadith5` table
of extra hadith outside the main numbering - included as its own trailing
set of chapters so none of that real content is dropped.
"""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Chapter, Page
from islamic_research_hub.shared.html_text_extraction import strip_html_to_text

LOGGER = logging.getLogger(__name__)

_SUPPLEMENTARY_TABLE_NAME = "hadith5"


class ShamilaUrduHadithReadError(Exception):
    """Raised when a Shamila Urdu hadith collection database cannot be read."""


class ShamilaUrduHadithReader:
    """Extract one hadith collection from its self-contained `.db` file."""

    def read(self, database_path: Path, category_name: str | None = "Hadith") -> Book:
        """Read metadata and every hadith, grouped into a Kitab/Baab table of contents."""
        try:
            with closing(self._connect_read_only(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                metadata = self._read_metadata(connection)
                rows = self._read_hadith_rows(connection)
        except sqlite3.Error as error:
            LOGGER.exception("Unable to read Shamila Urdu hadith collection: %s", database_path)
            raise ShamilaUrduHadithReadError(
                "The Shamila Urdu hadith database could not be read."
            ) from error

        pages = tuple(_build_page(index, row) for index, row in enumerate(rows, start=1))
        chapters = _build_chapters(rows)

        information = {
            "MJBN": database_path.stem,
            "Name": metadata.get("Book Name"),
            "ANAME": metadata.get("Writer") or metadata.get("Translator"),
            "PNAME": metadata.get("Publisher"),
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
        """Read the collection's own key/value metadata table."""
        rows = connection.execute("SELECT fieldName, fieldValue FROM metadata").fetchall()
        return {row["fieldName"]: row["fieldValue"] for row in rows if row["fieldValue"]}

    @staticmethod
    def _read_hadith_rows(connection: sqlite3.Connection) -> tuple[sqlite3.Row, ...]:
        """Read every hadith, main table first, then the supplementary table if present."""
        rows = list(connection.execute("SELECT * FROM hadith ORDER BY ID").fetchall())
        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if _SUPPLEMENTARY_TABLE_NAME in table_names:
            rows.extend(
                connection.execute(
                    f"SELECT * FROM {_SUPPLEMENTARY_TABLE_NAME} ORDER BY ID"
                ).fetchall()
            )
        return tuple(rows)


def _build_page(page_number: int, row: sqlite3.Row) -> Page:
    """Combine a hadith's Arabic text, Urdu translation, and grading into one page."""
    parts = [
        strip_html_to_text(row["HadithArabicText"]),
        strip_html_to_text(row["HadithUrduText"]),
    ]
    grade = row["HadithHukamAjmali"]
    if grade and grade.strip():
        parts.append(f"[{grade.strip()}]")
    content = "\n\n".join(part for part in parts if part)
    return Page(
        content_id=page_number,
        page_number=page_number,
        content_f=content or None,
        content_p=None,
        footnote=strip_html_to_text(row["HadithHashiaText"]),
    )


def _build_chapters(rows: tuple[sqlite3.Row, ...]) -> tuple[Chapter, ...]:
    """Group hadith rows into a Kitab (book) -> Baab (chapter) table of contents."""
    kitabs: list[Chapter] = []
    current_kitab_key: object = None
    current_kitab_baabs: list[Chapter] = []
    current_baab_key: object = None
    next_id = 1

    def flush_kitab() -> None:
        nonlocal current_kitab_baabs
        if kitabs and current_kitab_baabs:
            kitabs[-1] = _with_children(kitabs[-1], tuple(current_kitab_baabs))
        current_kitab_baabs = []

    for page_number, row in enumerate(rows, start=1):
        kitab_key = (row["KitabID"], row["KitabHiddenID"])
        kitab_title = (row["KitaabNameUrdu"] or row["KitaabNameArabic"] or "").strip()
        if kitab_title and kitab_key != current_kitab_key:
            flush_kitab()
            kitab_id = next_id
            next_id += 1
            kitabs.append(
                Chapter(
                    title_id=kitab_id,
                    title=kitab_title,
                    page_number=page_number,
                    parent_id=None,
                    sort_key=kitab_id,
                )
            )
            current_kitab_key = kitab_key
            current_baab_key = None

        baab_key = (row["BaabID"], row["BaabHiddenID"])
        baab_title = (row["BaabNameUrdu"] or row["BaabNameArabic"] or "").strip()
        if baab_title and kitabs and baab_key != current_baab_key:
            baab_id = next_id
            next_id += 1
            current_kitab_baabs.append(
                Chapter(
                    title_id=baab_id,
                    title=baab_title,
                    page_number=page_number,
                    parent_id=kitabs[-1].title_id,
                    sort_key=baab_id,
                )
            )
            current_baab_key = baab_key

    flush_kitab()
    return tuple(kitabs)


def _with_children(chapter: Chapter, children: tuple[Chapter, ...]) -> Chapter:
    """Return a copy of a chapter with its child chapters attached."""
    return Chapter(
        title_id=chapter.title_id,
        title=chapter.title,
        page_number=chapter.page_number,
        parent_id=chapter.parent_id,
        sort_key=chapter.sort_key,
        children=children,
    )
