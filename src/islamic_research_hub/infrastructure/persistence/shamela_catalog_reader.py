"""Reads Maktaba Shamela's book catalog (`book_index.db`).

Real, honest finding from direct inspection: individual Shamela `.mdb`
book files carry no title/author metadata at all - only page content and
table-of-contents headings. That metadata lives entirely in this separate
catalog file, keyed by `shamelaID` (the same number used as each real
book's `.mdb` filename, e.g. `1000.mdb` -> `shamelaID = 1000` - not the
catalog's own `id` column, and not `filePath`, which stores a stale
absolute path from wherever this Shamela install was first built).

Despite its `.db` extension, this file is plain SQLite (confirmed by its
own file header), unlike the individual book files - no 32-bit/COM
interop is needed to read it.
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ShamelaCatalogEntry:
    """One real book's catalog metadata - any field may be missing (the
    real data is sparse: most rows have no `authorName`)."""

    book_name: str | None
    author_name: str | None
    author_death: int | None
    category_id: int | None


class ShamelaCatalogReader:
    """Read `book_index.db`, Shamela's real title/author/category catalog."""

    def __init__(self, catalog_path: Path) -> None:
        self._catalog_path = catalog_path

    def load_by_shamela_id(self) -> dict[int, ShamelaCatalogEntry]:
        """Return every real catalog entry, keyed by `shamelaID` (unique
        across the whole catalog - confirmed by direct inspection: 36,042
        rows, 36,042 distinct `shamelaID` values)."""
        with closing(sqlite3.connect(self._catalog_path)) as connection:
            rows = connection.execute(
                "SELECT shamelaID, bookName, authorName, authorDeath, cat FROM books"
            ).fetchall()
        return {
            shamela_id: ShamelaCatalogEntry(
                book_name=book_name,
                author_name=author_name,
                author_death=author_death or None,
                category_id=category_id,
            )
            for shamela_id, book_name, author_name, author_death, category_id in rows
        }
