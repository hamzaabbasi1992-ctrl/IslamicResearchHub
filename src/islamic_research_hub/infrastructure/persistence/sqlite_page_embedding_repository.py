"""SQLite adapter for storing and searching page embeddings (pilot scale)."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from islamic_research_hub.domain.models.semantic_search_result import SemanticSearchResult

LOGGER = logging.getLogger(__name__)

EMBEDDING_DTYPE = np.float32


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
        self, embedding: tuple[float, ...], limit: int
    ) -> tuple[SemanticSearchResult, ...]:
        """Return the top matching pages ranked by cosine similarity."""
        try:
            with closing(sqlite3.connect(self._database_path)) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    """
                    SELECT
                        PageEmbeddings.BookID AS BookID,
                        PageEmbeddings.PageNo AS PageNo,
                        PageEmbeddings.Embedding AS Embedding,
                        Books.Title AS Title,
                        Books.Author AS Author,
                        Pages.Content AS Content
                    FROM PageEmbeddings
                    JOIN Books ON Books.BookID = PageEmbeddings.BookID
                    JOIN Pages
                        ON Pages.BookID = PageEmbeddings.BookID
                        AND Pages.PageNo = PageEmbeddings.PageNo
                    """
                ).fetchall()
        except sqlite3.Error as error:
            LOGGER.exception("Unable to search page embeddings: %s", self._database_path)
            raise PageEmbeddingError("Embeddings could not be searched.") from error

        if not rows:
            return ()

        matrix = np.stack(
            [np.frombuffer(row["Embedding"], dtype=EMBEDDING_DTYPE) for row in rows]
        )
        query_vector = np.asarray(embedding, dtype=EMBEDDING_DTYPE)
        similarities = matrix @ query_vector

        ranked_indices = np.argsort(similarities)[::-1][:limit]
        return tuple(
            SemanticSearchResult(
                book_id=rows[index]["BookID"],
                title=rows[index]["Title"],
                author=rows[index]["Author"],
                page_number=rows[index]["PageNo"],
                excerpt=_excerpt(rows[index]["Content"]),
                similarity=float(similarities[index]),
            )
            for index in ranked_indices
        )

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
