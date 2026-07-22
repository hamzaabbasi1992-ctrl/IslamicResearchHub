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
