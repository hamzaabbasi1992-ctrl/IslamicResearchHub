"""Read-only SQLite adapter for the Maktaba Shamila Urdu per-book database.

Each book is its own SQLite file with `Book` (ID, txt, fnotes),
`tableOfContents` (ID, pageID, txt, headingType), and `metadata`
(fieldName, fieldValue) tables - a different schema from Jibreel's
verified `.mjbz` format, but mapped onto the same `Book`/`Page`/`Chapter`
domain models so the rest of the pipeline (import, search, viewer) needs
no changes. Content is stored as HTML-styled spans; it is stripped to
plain text here since every other library in this corpus stores plain
text and search/display already assume that.
"""

import logging
import sqlite3
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Chapter, Page

LOGGER = logging.getLogger(__name__)


class ShamilaUrduBookReadError(Exception):
    """Raised when a Shamila Urdu book database cannot be read."""


class ShamilaUrduBookReader:
    """Extract one book from its self-contained Shamila Urdu `.db` file."""

    def read(self, database_path: Path, category_name: str | None = None) -> Book:
        """Read metadata, pages, footnotes, and table of contents for one book."""
        try:
            with closing(self._connect_read_only(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                metadata = self._read_metadata(connection)
                pages = self._read_pages(connection)
                chapters = self._read_chapters(connection)
        except sqlite3.Error as error:
            LOGGER.exception("Unable to read Shamila Urdu book: %s", database_path)
            raise ShamilaUrduBookReadError(
                "The Shamila Urdu database could not be read."
            ) from error

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
        """Read the book's own key/value metadata table."""
        rows = connection.execute("SELECT fieldName, fieldValue FROM metadata").fetchall()
        return {row["fieldName"]: row["fieldValue"] for row in rows if row["fieldValue"]}

    @staticmethod
    def _read_pages(connection: sqlite3.Connection) -> tuple[Page, ...]:
        """Read every content row, stripping HTML markup to plain text."""
        rows = connection.execute("SELECT ID, txt, fnotes FROM Book ORDER BY ID").fetchall()
        return tuple(
            Page(
                content_id=row["ID"],
                page_number=row["ID"],
                content_f=_strip_html(row["txt"]),
                content_p=None,
                footnote=_strip_html(row["fnotes"]) if row["fnotes"] else None,
            )
            for row in rows
        )

    @staticmethod
    def _read_chapters(connection: sqlite3.Connection) -> tuple[Chapter, ...]:
        """Read the table of contents as a flat list, skipping blank entries."""
        rows = connection.execute(
            "SELECT ID, pageID, txt FROM tableOfContents ORDER BY ID"
        ).fetchall()
        return tuple(
            Chapter(
                title_id=row["ID"],
                title=row["txt"].strip(),
                page_number=row["pageID"],
                parent_id=None,
                sort_key=row["ID"],
            )
            for row in rows
            if row["txt"] and row["txt"].strip()
        )


class _TextExtractingParser(HTMLParser):
    """Collect the visible text content of an HTML fragment."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def _strip_html(html_text: str | None) -> str | None:
    """Return the plain-text content of an HTML fragment, whitespace-collapsed."""
    if html_text is None:
        return None
    parser = _TextExtractingParser()
    parser.feed(html_text)
    text = " ".join(parser.text().split())
    return text or None
