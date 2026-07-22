"""Tests for the PageEmbeddingIndexer application service."""

from islamic_research_hub.application.page_embedding import PageEmbeddingIndexer


class FakeEmbedder:
    """Deterministic embedder returning one fixed-length vector per text."""

    def __init__(self) -> None:
        self.batches: list[tuple[str, ...]] = []

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Record the batch and return a vector derived from text length."""
        self.batches.append(texts)
        return tuple((float(len(text)), 0.0) for text in texts)


class FakeStore:
    """In-memory embedding store used to assert what was persisted."""

    def __init__(self) -> None:
        self.entries: list[tuple[int, int, tuple[float, ...]]] = []

    def store(self, entries: tuple[tuple[int, int, tuple[float, ...]], ...]) -> None:
        """Record every stored entry."""
        self.entries.extend(entries)


def test_index_pages_embeds_and_stores_every_page() -> None:
    """Every page is embedded and stored, preserving book id and page number."""
    embedder = FakeEmbedder()
    store = FakeStore()
    pages = (
        (1, 1, "First page content"),
        (1, 2, "Second page content"),
        (2, 1, "Another book's page"),
    )

    indexed_count = PageEmbeddingIndexer(embedder, store).index_pages(pages, batch_size=32)

    assert indexed_count == 3
    assert len(store.entries) == 3
    assert store.entries[0][0] == 1
    assert store.entries[0][1] == 1


def test_index_pages_respects_batch_size() -> None:
    """Pages are embedded in batches no larger than the configured batch size."""
    embedder = FakeEmbedder()
    store = FakeStore()
    pages = tuple((1, page_number, "content") for page_number in range(1, 6))

    PageEmbeddingIndexer(embedder, store).index_pages(pages, batch_size=2)

    assert [len(batch) for batch in embedder.batches] == [2, 2, 1]
