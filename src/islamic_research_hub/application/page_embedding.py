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
        commit_batch_size: int = 1000,
    ) -> int:
        """Embed and store every (book_id, page_number, content) triple.

        `batch_size` bounds how many pages are embedded at once (keeps the
        embedding model's peak memory use predictable). `commit_batch_size`
        is a separate, larger threshold for how many embedded entries
        accumulate before a single `store()` call - decoupling the two
        matters because each `store()` call is its own SQLite transaction:
        committing every 32-page embedding batch (the pilot run's real
        behavior before this fix) cost ~789 MB of transaction/journal
        overhead for what should have been ~12.6 MB of real vector data.
        """
        indexed_count = 0
        pending: list[tuple[int, int, tuple[float, ...]]] = []
        for start in range(0, len(pages), batch_size):
            batch = pages[start : start + batch_size]
            embeddings = self._embedder.embed(tuple(content for _, _, content in batch))
            pending.extend(
                (book_id, page_number, embedding)
                for (book_id, page_number, _), embedding in zip(
                    batch, embeddings, strict=True
                )
            )
            if len(pending) >= commit_batch_size:
                self._store.store(tuple(pending))
                indexed_count += len(pending)
                pending.clear()
        if pending:
            self._store.store(tuple(pending))
            indexed_count += len(pending)
        return indexed_count
