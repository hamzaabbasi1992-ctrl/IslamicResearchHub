# Changelog

## Unreleased

### Added

- `BookLibraryExporter` (`infrastructure/reporting/book_library_exporter.py`), which writes each successfully scanned book as a standalone Markdown file under `library/<subject>/<title>.md`. Subject is resolved by walking the book's own `MJCN` category placement up to its root ancestor; titles/subjects are sanitized for the filesystem, and same-run title collisions across different sources are disambiguated by source filename rather than silently overwritten. Wired into the CLI right after the existing library report export.
- Indexes on `BookID` for the `Categories`, `Chapters`, and `Pages` tables in the master database, and `FOREIGN KEY (BookID) REFERENCES Books(BookID)` declarations on the same three tables, so per-book lookups no longer require a full table scan.
- An FTS5 full-text index (`PagesFTS`) over `Pages.Content`, kept in sync automatically via an `AFTER INSERT` trigger on `Pages`. This is the first search primitive for the project's search-engine goal.
- A one-time backfill that rebuilds `PagesFTS` from any pages imported before the index existed, so previously-built master databases become searchable without a full re-scan.
- Tests covering the new indexes, FTS sync on import, and the backfill path (`tests/test_master_book_repository.py`).
- `SearchResult` domain model (`domain/models/search_result.py`).
- `BookSearchService` application service (`application/book_search.py`) validating queries (non-empty, positive limit) against a `SearchIndex` port.
- `SqliteBookSearchRepository` (`infrastructure/persistence/sqlite_book_search_repository.py`), a read-only adapter that queries the existing `PagesFTS` index, ranked by `bm25` relevance (`ORDER BY rank`), returning book title/author/page number and a highlighted excerpt via FTS5's `snippet()`.
- `search_cli.py` (`interfaces/search_cli.py`), a new, separate CLI entry point (`python -m islamic_research_hub.interfaces.search_cli "query"`) — kept independent from the existing scan CLI so `python -m islamic_research_hub <folder>` is unchanged.
- Tests for the search service, search repository, and search CLI (`tests/test_book_search.py`, `tests/test_sqlite_book_search_repository.py`, `tests/test_search_cli.py`).
- README section documenting the new search command.

### Notes

- Schema changes are additive only (`CREATE ... IF NOT EXISTS`); existing `data/books.db` files pick up the new indexes and FTS index on their next import run without needing to be rebuilt from scratch.
- The search command is a separate entry point rather than a subcommand of the existing CLI, specifically to avoid any argparse restructuring risk to the working scan command.
- Real-data validation: ran the full scan/export/import pipeline against the actual 2,322-file library. 2,322/2,322 extracted, 0 failures, 922,345 pages, 696,791 chapters. Markdown export: 2,322/2,322 written. Keyword search validated against real Urdu/Arabic content with correct ranking, titles, and snippets.

## Semantic search pilot (not yet scaled to the full corpus)

### Added

- Optional `ai` dependency group (`pyproject.toml`) pinning `sentence-transformers>=5`, installed via `pip install -e .[ai]`.
- `SemanticSearchResult` domain model (`domain/models/semantic_search_result.py`).
- `PageEmbeddingIndexer` + `TextEmbedder`/`EmbeddingStore` ports (`application/page_embedding.py`) for building an embedding index in batches.
- `SemanticBookSearchService` + `SemanticSearchIndex` port (`application/semantic_book_search.py`), validating queries the same way as the keyword `BookSearchService`.
- `SentenceTransformerEmbedder` (`infrastructure/ai/sentence_transformer_embedder.py`) — local, multilingual (`paraphrase-multilingual-MiniLM-L12-v2`), CPU-only on this machine (no GPU detected).
- `SqlitePageEmbeddingRepository` (`infrastructure/persistence/sqlite_page_embedding_repository.py`) — a new `PageEmbeddings` table storing normalized embeddings as BLOBs, with brute-force cosine-similarity search via `numpy`. Explicitly a pilot-scale implementation (loads all embeddings into memory to score), not an ANN index.
- `semantic_index_cli.py` and `semantic_search_cli.py` (`interfaces/`) — separate pilot entry points for building and querying the embedding index for one subject at a time, resolved by walking each book's stored category chain to its root (same logic as `BookLibraryExporter`, reimplemented against DB rows rather than in-memory `Book` objects).
- Tests using fake embedders/stores (no real model load in the test suite) plus real-SQLite storage/search round-trip tests.

### Pilot run results (حدیث شریف / Hadith subject, 27 books, 8,179 pages)

- Search quality: strong. Queries return conceptually related passages that don't share the literal query words (verified against real content).
- Timing: ~9.4 minutes of CPU encoding for 8,179 pages (~14.5 pages/sec, no GPU). Extrapolated to the full 922,345-page corpus: ~17-18 hours of CPU time.
- Storage finding: the embedding data itself is correct and compact (verified: 8,179 rows, no duplicates, exactly 1536 bytes/vector), but `data/books.db` grew ~789 MB on disk for what should be ~12.6 MB of vector data — likely from committing every 32-page batch as a separate transaction (256 commits for this pilot). Should be fixed (larger/fewer commits) before any full-corpus run.
- Decision: pilot validated the approach; full-corpus indexing is intentionally on hold pending a decision on when/whether to commit ~18 hours of CPU time.
