"""Application service for building a semantic embedding index over pages."""

from typing import Protocol


class TextEmbedder(Protocol):
    """Contract for turning text into a fixed-size embedding vector."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Return one embedding vector per input text, in the same order."""


class EmbeddingStore(Protocol):
    """Contract for persisting page embeddings."""

    def store(self, entries: tuple[tuple[int, int, tuple[float, ...]], ...]) -> None:
        """Persist (book_id, page_number, embedding) triples."""


class PageEmbeddingIndexer:
    """Coordinate embedding generation and storage for a batch of pages."""

    def __init__(self, embedder: TextEmbedder, store: EmbeddingStore) -> None:
        self._embedder = embedder
        self._store = store

    def index_pages(
        self,
        pages: tuple[tuple[int, int, str], ...],
        batch_size: int = 32,
    ) -> int:
        """Embed and store every (book_id, page_number, content) triple."""
        indexed_count = 0
        for start in range(0, len(pages), batch_size):
            batch = pages[start : start + batch_size]
            embeddings = self._embedder.embed(tuple(content for _, _, content in batch))
            entries = tuple(
                (book_id, page_number, embedding)
                for (book_id, page_number, _), embedding in zip(
                    batch, embeddings, strict=True
                )
            )
            self._store.store(entries)
            indexed_count += len(entries)
        return indexed_count
