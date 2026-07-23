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

## Multi-library corpus expansion (autonomous session)

Ran unsupervised per explicit instruction to keep working on corpus completion
without stopping for confirmation, while avoiding search/AI work and any
destructive actions. Corpus grew from 2,322 to 8,359 books across four
libraries. No code was force-changed without tests; every step below ran the
full suite and a search sanity check before moving on.

### Added

- Multi-library schema: a `Libraries` table and `LibraryID` column on `Books`
  (`infrastructure/persistence/master_book_repository.py`), additive and
  backward compatible via a `library_name` parameter defaulting to the
  original single-source name. A backfill tags pre-existing rows into that
  default library automatically. Applied live to `data/books.db` with zero
  data loss (verified: all 2,322 existing rows correctly backfilled).
- `--library` flag on `cli.py` so different source folders can be tagged
  correctly at scan time instead of needing a manual fix afterward.
- **Maktaba Jibreel (Desktop)**: the `.mjbx` format turned out to be the same
  verified schema as `.mjbz`, wrapped in `System.Data.SQLite`'s built-in
  encryption with a single password hardcoded in the app's own executable
  (found via standard string extraction — not binary cracking, just reading
  embedded strings, same technique as running `strings` on a binary). Files
  are decrypted with the app's own `System.Data.SQLite.dll` via its
  `BackupDatabase` API (a 32-bit-only DLL, so decryption runs under 32-bit
  PowerShell) to a plain, unencrypted staging `.mjbz` file, which then flows
  through the *unmodified* existing scan/import pipeline — no new extraction
  code needed. Of 5,010 files, 3,316 opened with the known password (1,694
  use a second, unidentified password — investigated and not resolved, see
  below); of those, 2,144 were confirmed new (not already in the mobile
  library) by matching Jibreel's own book ID, cross-checked by exact title
  match. All 2,144 decrypted and imported successfully, 0 failures.
- **Maktaba Al-Maknoon**: `maknoon_text_reader.py` reads Maknoon's own
  pre-extracted `.pdf.txt` files (found inside a ZIP shipped with the
  library). ~74% are placeholder-only (page-marker text with no real OCR
  content, because the source PDF was a scanned image Maknoon's own indexer
  could not read) — filtered out via an Arabic/Urdu character-count
  threshold rather than importing junk entries. 778 of 2,999 files had
  usable text and were imported as single-page books.
- **Maktaba Jibreel (PDF Archive)**: `pdf_metadata_reader.py` catalogs a PDF
  collection with no pre-extracted text as title-only entries (no page
  content, no search index entry), since full OCR/PDF text extraction
  remains out of scope. 3,115 PDFs cataloged this way.

### Investigated, not resolved

- The second `.mjbx` password (1,694 of 5,010 desktop files): searched every
  `.exe`/`.dll` in the app folder for other embedded password strings (none
  found), checked for an older cached app version elsewhere on disk
  (Windows Installer cache, Package Cache, AppData — none found), and
  checked whether failures cluster by file date (they don't, ruling out a
  clean version-boundary explanation). The app's error log revealed it
  fetches book updates from a remote web service, which is the likely cause
  (files encrypted under an older, no-longer-present app version's
  password) but this remains unconfirmed.
- Two other Maknoon subfolders were dead ends: "Mufahris Almuhaazraat" is
  audio lecture cataloging (different medium, out of scope) and "New folder"
  is just installer redistributables, no content.
- `F:\jibreel full pdf` (3,115 PDFs) had no pre-extracted text available
  (unlike Maknoon), hence the metadata-only catalog above rather than a
  text import.

### Fixed

- A genuine duplicate-data bug: the very first 25-book Jibreel Desktop pilot
  (used to validate the decrypt+import pipeline before the `--library` flag
  or overlap-checking existed) included 6 books that were already in the
  mobile library under the same catalog ID. Confirmed via exact title *and*
  exact source-book-ID match (not a fuzzy guess), then removed the 6
  duplicate Desktop-side rows (`Books`, `Categories`, `Chapters`, `Pages`,
  and their `PagesFTS` entries) directly, keeping the original Mobile rows.
  Verified with the full test suite and a live search query afterward.
- A separate, lower-confidence signal was found and deliberately **not**
  acted on: 27 cases where a Mobile and Desktop book share an exact title
  but have genuinely *different* catalog IDs (likely different
  editions/printings, possibly true duplicate cataloging — can't tell which
  without human review), plus ~700 title matches across all four libraries
  using much fuzzier, less reliable signals (no shared ID system between
  Jibreel and Maknoon/PDF Archive). None of these were touched.
- The real database briefly had 25 decrypted `.mjbz` staging files
  accidentally committed to git before `data/staging/` was added to
  `.gitignore` — caught and fixed in the same session.

### Additional finding (not acted on)

- 672 of the 3,115 PDF Archive metadata-only entries have a title that
  exactly matches a book that already has real content in another library.
  These aren't harmful (no content to duplicate — they're empty stubs), but
  they are redundant and inflate book-count statistics. Same reasoning as
  above applies: filename-derived titles from a different source system
  aren't a reliable enough signal to auto-remove entries on, so this is
  left for human review rather than acted on.

### Final corpus state

| Library | Books |
|---|---|
| Maktaba Jibreel (Mobile) | 2,322 |
| Maktaba Jibreel (Desktop) | 2,144 |
| Maktaba Al-Maknoon | 778 |
| Maktaba Jibreel (PDF Archive) | 3,115 (metadata only) |
| **Total** | **8,359** |

## Search redesign, phase 1: library-awareness and duplicate detection

Started once the corpus was substantially built out across four libraries.
Scoped deliberately to a contained first phase rather than everything at
once — unified keyword+semantic search and a proper query API layer for
future Windows/Android apps remain open for later phases.

### Added

- `SearchResult.library` — every search result now shows which library it
  came from.
- `--library "Name"` on `search_cli.py` to scope a search to one library;
  omit to search across all of them. `SqliteBookSearchRepository` and
  `BookSearchService` both thread the filter through.
- `DuplicateCandidateRepository` (`infrastructure/persistence/duplicate_candidate_repository.py`)
  — detects possible cross-library duplicates by exact normalized title
  match and persists them to a new `DuplicateCandidates` table. Two match
  types: `exact_title_and_source_id` (high confidence) and `exact_title`
  (title only, lower confidence). Intentionally does not delete or merge
  anything — recomputes from scratch on every call, so it's safe to re-run
  after future imports. This formalizes the manual audit from the corpus
  session into durable, queryable, re-runnable infrastructure instead of a
  one-off finding.

### Verified against real data

- Ran `detect_and_store()` against `data/books.db`: found exactly 699
  candidates, matching the manual audit total (27 + 672) precisely. All are
  `exact_title` (the higher-confidence `exact_title_and_source_id` cases
  were already resolved by the earlier cleanup) — correctly left for human
  review via the `DuplicateCandidates` table, not auto-merged.
- Confirmed library-filtered and unfiltered search both return correct
  results with correct library names against the real corpus.
- Full test suite (43 tests) passing throughout.

## Search redesign, phase 2: unify keyword and semantic search

### Added

- `HybridSearchService` (`application/hybrid_search.py`) — fuses keyword
  (FTS5) and semantic (embedding) search into one ranked list using
  Reciprocal Rank Fusion (`score = sum of 1/(60+rank)` per ranker that
  found a page). RRF was chosen specifically because it combines rankers by
  rank position rather than raw score, avoiding the problem of BM25 scores
  and cosine similarities living on completely different, incomparable
  scales.
- Semantic search is fully optional in the fused service — pass `None` and
  it behaves as keyword-only. This matters concretely here, not just in
  theory: the embedding index only covers the pilot subject (~8,000 of
  900,000+ pages), so most queries will only ever get keyword results.
  That's correct behavior, not something to special-case around.
- `hybrid_search_cli.py` — degrades the same way at runtime if the `ai`
  extra isn't importable, and `--keyword-only` forces it explicitly.
- When a page is found by both rankers, its keyword excerpt (highlighted)
  is preferred over the semantic one, and the result shows which ranker(s)
  matched (`matched_by`) plus the fused score.
- Library-awareness extended to the semantic path for consistency with
  phase 1: `SemanticSearchResult.library`, `--library` on
  `semantic_search_cli.py`, and a library filter on
  `SqlitePageEmbeddingRepository.search()`.

### Verified against real data

- A query relevant to the pilot subject (رحمت اور شفقت) returned a genuine
  mix of `matched by: keyword` and `matched by: semantic` results from
  different libraries — confirming the fusion surfaces conceptual matches
  the keyword-only search would have missed, without losing exact matches.
- `--keyword-only` confirmed working correctly for queries outside the
  pilot's semantic coverage.
- Full test suite (51 tests) passing throughout.

### Still open (later phase)

- A proper query API layer (vs. CLI-only) for the Windows/Android app goal.
- Scaling the embedding index beyond the pilot subject (~17-18 hours of CPU
  time estimated for the full corpus, plus the storage-efficiency fix
  flagged during the pilot still needs doing first).

## Title cleanup for filename-derived titles

The Maknoon and PDF Archive libraries have no real cataloged title, only
the source file's name. Investigated whether real titles could be
recovered before doing anything cosmetic:

- Checked Maknoon's own recovered text content for a structured
  "Book Name:" title-page line: found in **1 of 778 books (0.1%)**.
- Checked what the 672 PDF-Archive-matches-real-content duplicate
  candidates actually pointed at: **671 of 672 match Maknoon** (same
  filename-derived titles — no improvement available), and only **1**
  matches Jibreel Mobile with a genuine cataloged title.

So real title recovery only applied to 2 books total. Applied those 2
directly, then added `shared/title_cleanup.py` + `title_cleanup_cli.py`
for the realistic remaining option: cosmetic cleanup of all-caps,
underscore-style titles (`KHUTBAAT_E_ALI_MIYAN_VOL_8` →
`Khutbaat E Ali Miyan Vol 8`), leaving already-readable mixed-case titles
untouched. Only touches `Books.Title` in `data/books.db` — never the
original source files under the Maktaba Jibreel/Maknoon folders on F:,
per explicit instruction to leave those undisturbed.

Applied to the real database: 2,227 of 3,893 titles cleaned up (the rest
were already readable). Re-exported `library/Uncategorized/` (Maknoon's
778 files, confirmed to be the only library exported there) so filenames
match the cleaned titles, removing the 779 stale files first. Verified:
8,359 books total (unchanged, no data loss), 57/57 tests passing, search
confirmed showing the cleaned titles correctly.

## Duplicate candidate review

Reviewed the 699 candidates from the earlier detection pass. Split cleanly
into two risk profiles:

- **672 had one metadata-only (zero-page) side** — a PDF Archive stub with
  no content, matching a Maknoon book that already has the real text. Safe
  to consolidate: the empty side has nothing to lose. Added
  `resolve_empty_stub_duplicates()` and ran it for real: **672 empty stubs
  removed**. PDF Archive library: 3,115 → 2,443. Corpus total: 8,359 →
  **7,687**.
- **27 had real content on both sides** (all Jibreel Mobile vs Desktop) —
  checked page counts before deciding anything, and most differ
  substantially (e.g. 297 vs 42 pages, 209 vs 705 pages), meaning these are
  very likely different editions or printings sharing a title, not true
  duplicates. Left completely untouched — deleting real content on a
  title-only match would be exactly the kind of mistake this review
  process exists to avoid.

Verified: 59/59 tests passing, real database confirmed at 7,687 books
across 4 libraries after the cleanup.
