"""SQLite adapter for storing and searching page embeddings (pilot scale)."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from islamic_research_hub.domain.models.semantic_search_result import SemanticSearchResult
from islamic_research_hub.shared.language_names import canonical_language_name

LOGGER = logging.getLogger(__name__)

EMBEDDING_DTYPE = np.float32

SAME_LANGUAGE_BOOST = 0.10
"""Added to a candidate page's raw cosine similarity when its own real
`Books.Language` matches the query's detected language, before ranking.

Real, measured value, not guessed: checked directly against this
corpus's actual ~1.7M embedded pages (Arabic ~10%, Urdu ~67%,
unlabeled ~12%) with two real Arabic queries confirmed broken
(`أحكام الطلاق في الفقه الإسلامي`, `فضل الصيام`) - the best real
Arabic-labeled match for one of them scored 0.8026 while rank 50 sat at
0.8368, so it never appeared in a real top-50 at all despite genuinely
matching the query. Tried 0.03/0.05/0.08/0.10/0.15 against both real
queries: 0.10 was the smallest value that produced a real, meaningful
same-language recovery on both (14/50 and 9/50 Arabic results,
respectively) without one query's results flipping to Arabic-only
noise the way 0.15 did (37/50) - a correction, not an override. A page
with no recorded `Books.Language` gets no boost either way (there's no
real per-page language to compare against without reading its full
text at query time, which the brute-force scan is already too slow to
do here) - this only ever helps a same-language match compete, never
penalizes anything."""


class PageEmbeddingError(Exception):
    """Raised when page embeddings cannot be stored or searched."""


class SqlitePageEmbeddingRepository:
    """Store page embeddings as BLOBs and search them by brute-force cosine similarity.

    This is a pilot-scale implementation: search loads every stored embedding
    into memory and scores it with one vectorized dot product (embeddings are
    expected to be pre-normalized, so dot product equals cosine similarity).
    It is meant to validate embedding quality on a small subject before
    deciding on a proper approximate-nearest-neighbor index for the full
    922,000-page library.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def ensure_schema(self) -> None:
        """Create the `PageEmbeddings` table if it doesn't exist yet, writing no rows.

        Lets a caller (e.g. a resume-aware indexing run) safely query
        `PageEmbeddings` - to see what's already indexed - before any real
        embedding has ever been stored, without duplicating the schema
        declaration from `store()`.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.commit()

    def store(self, entries: tuple[tuple[int, int, tuple[float, ...]], ...]) -> None:
        """Persist (book_id, page_number, embedding) triples."""
        if not entries:
            return
        try:
            with closing(sqlite3.connect(self._database_path)) as connection:
                self._create_schema(connection)
                connection.executemany(
                    """
                    INSERT INTO PageEmbeddings (BookID, PageNo, Embedding)
                    VALUES (?, ?, ?)
                    ON CONFLICT (BookID, PageNo) DO UPDATE SET Embedding = excluded.Embedding
                    """,
                    (
                        (
                            book_id,
                            page_number,
                            np.asarray(embedding, dtype=EMBEDDING_DTYPE).tobytes(),
                        )
                        for book_id, page_number, embedding in entries
                    ),
                )
                connection.commit()
        except sqlite3.Error as error:
            LOGGER.exception("Unable to store page embeddings: %s", self._database_path)
            raise PageEmbeddingError("Embeddings could not be written.") from error

    def search(
        self,
        embedding: tuple[float, ...],
        limit: int,
        library: str | None = None,
        query_language: str | None = None,
    ) -> tuple[SemanticSearchResult, ...]:
        """Return the top matching pages ranked by cosine similarity.

        When `library` is given, results are restricted to that library
        name. When `query_language` is given, a page whose own recorded
        `Books.Language` matches it gets `SAME_LANGUAGE_BOOST` added to
        its similarity before ranking - see that constant's own
        docstring for the real, measured evidence behind it.

        Two real, tested fixes over the original implementation, at
        ~600K embedded pages:

        1. Two-phase query, not one big join: scoring only ever needs
           (BookID, PageNo, Embedding) - joining in `Books.Title`/
           `Author`/`Pages.Content`/`Libraries.Name` for *every*
           embedded page (not just the real top `limit` results) meant
           fetching full page text for hundreds of thousands of rows
           just to discard nearly all of them after ranking. Real
           metadata is now looked up only for the results actually
           returned.
        2. One `np.frombuffer` call, not one per row: building the
           scoring matrix via `[np.frombuffer(row["Embedding"], ...)
           for row in rows]` then `np.stack(...)` does real per-row
           Python-level work hundreds of thousands of times. Embedding
           BLOBs are fixed-width, so concatenating them into a single
           buffer first and reshaping once is equivalent and avoids
           that per-row cost entirely.

        Confirmed for real: these two fixes together brought one real
        production search from ~95 seconds down to a few seconds at
        ~600K embedded pages (see CHANGELOG for exact before/after
        numbers) - this is still a brute-force scan (cost still grows
        with corpus size, unlike a real ANN index), just no longer
        paying for work it doesn't need.
        """
        needs_language = query_language is not None
        try:
            with closing(sqlite3.connect(self._database_path)) as connection:
                cursor = connection.cursor()
                needs_books_join = library is not None or needs_language
                sql = """
                    SELECT
                        PageEmbeddings.BookID,
                        PageEmbeddings.PageNo,
                        PageEmbeddings.Embedding
                """
                sql += ", Books.Language" if needs_language else ""
                sql += " FROM PageEmbeddings"
                parameters: list[object] = []
                if needs_books_join:
                    sql += " JOIN Books ON Books.BookID = PageEmbeddings.BookID"
                if library is not None:
                    sql += (
                        " JOIN Libraries ON Libraries.LibraryID = Books.LibraryID"
                        " WHERE Libraries.Name = ?"
                    )
                    parameters.append(library)
                rows = cursor.execute(sql, parameters).fetchall()

                if not rows:
                    return ()

                keys = [(row[0], row[1]) for row in rows]
                buffer = b"".join(row[2] for row in rows)
                matrix = np.frombuffer(buffer, dtype=EMBEDDING_DTYPE).reshape(len(rows), -1)
                query_vector = np.asarray(embedding, dtype=EMBEDDING_DTYPE)
                similarities = matrix @ query_vector

                # Boost only decides ranking order below - the real,
                # unboosted cosine similarity is still what's returned
                # to the caller as each result's `similarity`, so the
                # displayed match confidence stays honest.
                ranking_similarities = similarities
                if needs_language:
                    same_language = np.array(
                        [canonical_language_name(row[3]) == query_language for row in rows]
                    )
                    ranking_similarities = similarities + np.where(
                        same_language, SAME_LANGUAGE_BOOST, 0.0
                    )

                ranked_indices = np.argsort(ranking_similarities)[::-1][:limit]
                top_keys = [keys[index] for index in ranked_indices]
                connection.row_factory = sqlite3.Row
                metadata = self._load_metadata(connection, top_keys)
        except sqlite3.Error as error:
            LOGGER.exception("Unable to search page embeddings: %s", self._database_path)
            raise PageEmbeddingError("Embeddings could not be searched.") from error

        return tuple(
            SemanticSearchResult(
                book_id=key[0],
                title=metadata[key]["Title"],
                author=metadata[key]["Author"],
                page_number=key[1],
                excerpt=_excerpt(metadata[key]["Content"]),
                similarity=float(similarities[index]),
                library=metadata[key]["Library"],
            )
            for index, key in zip(ranked_indices, top_keys, strict=True)
        )

    @staticmethod
    def _load_metadata(
        connection: sqlite3.Connection, keys: list[tuple[int, int]]
    ) -> dict[tuple[int, int], sqlite3.Row]:
        """Fetch title/author/content/library only for the given (BookID, PageNo) pairs."""
        metadata: dict[tuple[int, int], sqlite3.Row] = {}
        for book_id, page_no in keys:
            row = connection.execute(
                """
                SELECT Books.Title AS Title, Books.Author AS Author,
                       Pages.Content AS Content, Libraries.Name AS Library
                FROM Books
                LEFT JOIN Pages ON Pages.BookID = Books.BookID AND Pages.PageNo = ?
                LEFT JOIN Libraries ON Libraries.LibraryID = Books.LibraryID
                WHERE Books.BookID = ?
                """,
                (page_no, book_id),
            ).fetchone()
            metadata[(book_id, page_no)] = row
        return metadata

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        """Create the pilot embeddings table when it does not yet exist."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS PageEmbeddings (
                BookID INTEGER NOT NULL REFERENCES Books(BookID),
                PageNo INTEGER NOT NULL,
                Embedding BLOB NOT NULL,
                PRIMARY KEY (BookID, PageNo)
            );
            """
        )


def _excerpt(content: str | None, max_length: int = 300) -> str:
    """Return a bounded excerpt of page content for display."""
    if content is None:
        return ""
    normalized = " ".join(content.split())
    return normalized if len(normalized) <= max_length else normalized[:max_length] + "..."
