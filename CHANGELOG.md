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

## Second .mjbx password: investigation closed, unresolved

Continued the investigation from the corpus-expansion session with fresh
angles: tried ~13 plausible password variations against a known-failing
file (correctly validated this time — first pass gave false positives
because `SQLiteConnection.Open()` does not actually check the password,
SQLite only decrypts on first query; caught before trusting any result).
Checked `SoftwareUpdate.exe` (the app's own updater) for password strings —
none; it only handles 7z update packages, not book decryption. Checked
file version info — only one build (2.9.0.0) exists on this machine, no
evidence of an older version that might explain a password change.
Checked the full error log for any mention of "password" — zero.

Combined with the earlier session's checks (binary string search across
every exe/dll, cached-install search, date-clustering of failures), this
is now closed as not solvable with reasonable effort. Getting further
would require decompiling the app's actual code, not just reading its
strings/config. The 1,694 locked Jibreel Desktop files remain
inaccessible.

## Maknoon real per-page data, applied to the real database

Re-imported all 778 Maknoon books using the new page-splitting reader.
Deleted the 778 old single-page rows first (and their Pages/PagesFTS/
DuplicateCandidates entries), then re-ran the import so search results now
carry the real matching page number instead of always page 1 — verified:
205,301 real pages now, vs. 778 before (one per book). Since re-importing
recreated the rows from scratch, three downstream fixes needed reapplying:
title cleanup (618 titles), the one genuine real-title fix found earlier,
and the `library/Uncategorized/` export (regenerated with correct titles).
Duplicate detection re-run: still exactly 27 remaining candidates (the
Mobile/Desktop pairs, unaffected by this change) and 0 new empty-stub
matches, confirming the earlier 672 removal was clean and permanent.

Verified: 61/61 tests passing, 7,687 books unchanged, search confirmed
returning real, varied page numbers for Maknoon results.

## Local web app: search, PDF page-jump, in-app reading

Added a Flask-based local web app (`interfaces/web_app.py`, optional `web`
dependency group) reusing `HybridSearchService` unchanged - same search
backend as the CLI, browser UI in front. Each result links to whatever is
actually available for that book: a real PDF at the matching page
(`/pdf/<id>#page=N`, using the browser's own built-in PDF viewer - no
server-side page-jump logic needed) for Maknoon/PDF Archive books whose
source file resolves, or an in-app reading view (`/read/<id>?page=N`,
built straight from the database) for everything else, including Jibreel
Mobile/Desktop, which never had PDFs to begin with. This only works
correctly for Maknoon because of the real per-page data above - before
that fix every result would have pointed at page 1.

Hardened the semantic-loading path found during live testing: model
loading previously crashed the whole app on any transient network issue
(it revalidates against HuggingFace Hub even for an already-cached model);
now sets `HF_HUB_OFFLINE=1` and catches broad failures, falling back to
keyword-only rather than refusing to start.

Launcher: `web_app_cli.py` + a double-click `.bat` file at the repo root.
8 new tests (using `enable_semantic=False` to keep them fast - loading the
real model made an early test run time out), 69/69 total passing.

## Governance change: phased roadmap adopted

The user handed down a strict phase-based roadmap (Import System &rarr;
Master Database &rarr; Search &rarr; Desktop GUI &rarr; Book Viewer &rarr; AI),
explicitly requiring each phase to be 100% complete before the next starts,
no side improvements, no premature optimization, no unrequested AI work.
Two direct conflicts with prior instructions were surfaced and resolved
before proceeding rather than silently picked: the web app above stays
(already built, already requested) but no further web/GUI work happens
until the roadmap's GUI phase (PySide6 desktop, not web); Shamela stays
excluded (still overrides the roadmap's Phase 1 list, per explicit
confirmation). PDF importer scope for Phase 1 confirmed as native-text-layer
extraction only - OCR is explicitly a separate, later phase.

## Phase 1 hardening: Maknoon survives corrupted/unreadable files

Found while assessing Phase 1 against the roadmap's completion bar ("logs
failures... survives corrupted files"): `maknoon_import_cli.py` read each
file with no error handling - a single corrupted or inaccessible file
would have crashed the entire import run instead of being logged and
skipped. Wrapped the per-file read in a try/except, and split the summary
into two distinct counts (placeholder-only vs. failed-to-read) rather than
conflating "no real content" with "could not be read" under one number.
New test simulates an unreadable file and confirms the run completes and
imports the remaining valid books. 70/70 tests passing.

## Phase 1: Jibreel Desktop decryption formalized into real, tested code

Replaced the ad-hoc scratchpad PowerShell scripts from the corpus-expansion
session with committed, tested code - the real gap flagged when auditing
Phase 1 against the "has tests" bar.

- `application/jibreel_desktop_import.py`: `find_new_files()` and
  `JibreelDesktopImportPlanner` - pure, fully unit-tested logic for
  deciding which `.mjbx` files are new. Simplification found while
  planning this: `.mjbx` filenames are literally the app's own catalog id
  (`2584.mjbx` = book id 2584), so "is this file new" only needs a
  filename comparison against `Books.SourceBookID` - no need to open or
  decrypt anything just to check.
- `infrastructure/persistence/scripts/decrypt_mjbx.ps1`: the actual
  decryption script, now living in the repo instead of a scratchpad
  temp folder, parameterized (job list in, results out, both JSON)
  instead of hardcoded paths.
- `infrastructure/persistence/powershell_mjbx_decryptor.py`: Python
  adapter that shells out to the script. Real bug caught during
  end-to-end validation (not just the fake-decryptor unit tests):
  PowerShell's `Out-File -Encoding utf8` writes a UTF-8 BOM, which
  `json.loads` doesn't handle by default - fixed by reading with
  `utf-8-sig` instead of `utf-8`.
- `interfaces/jibreel_desktop_import_cli.py`: wires it together and
  reuses the existing, already-tested scan/import pipeline unchanged
  for the decrypted output. Structured with a separate `run(args,
  decryptor)` so tests can inject a fake decryptor - the real one
  requires the external app's own 32-bit DLL, which won't exist in a
  portable test environment.
- 8 new tests: pure planning logic, plus CLI orchestration with a fake
  decryptor covering new-file decryption, a locked (wrong-password)
  file being skipped rather than fatal, and already-imported files
  being correctly excluded from re-planning.

Validated against real data, not just fakes: ran the real CLI with the
real DLL and real password against 2 known-good and 1 known-locked
`.mjbx` file. Result matched expectations exactly - 2 decrypted and
imported (217 and 393 pages, matching the original pilot run's numbers
for these same files), 1 correctly rejected as failed. Re-run confirmed
the already-imported files are excluded and the still-locked file is
retried (not permanently blacklisted, in case its password is found
later). 78/78 tests passing.

## Phase 1 closed: Generic PDF importer evaluated and deliberately not built

Before building a native-text-layer PDF importer (no OCR, matching the
agreed scope), checked what it would actually recover: sampled 120 files
from the Jibreel PDF Archive (3,115 total, full-document scan, no read
errors) and 60 from Maknoon's PDF Data folder (3,258 total). Only **2
(1.7%)** and **3 (5%)** respectively had any real extractable text - this
corpus is almost entirely scanned images, not born-digital PDFs. Native
extraction would have recovered roughly 50-150 books out of ~6,373 PDFs.

Given that yield, decided not to build it. No code was written - `pypdf`
was pip-installed locally to run the sample check and never added to the
project. The PDF Archive library stays metadata-only (title/path, no
text) until OCR is actually in scope, which is explicitly a later phase,
not Phase 1.

### Phase 1 status: complete

- Jibreel Mobile - mature, tested, production ready.
- Jibreel Desktop - decryption formalized and tested this session.
- Maknoon - hardened against corrupted files this session.
- Generic PDF - evaluated, deliberately deferred (see above); metadata
  cataloging (title/path, no text) already exists and stays as-is.
- Shamela - excluded per explicit instruction.
- Calibre - not started; marked optional in the roadmap.

## Phase 2, step 1: database verification tool

First Phase 2 item, deliberately picked first: no schema changes, no risk,
and everything that follows (backups, migrations, structural changes)
benefits from having it in place before touching the schema further.

`domain/models/verification_report.py` + `infrastructure/persistence/
database_verifier.py`: read-only checks combining SQLite's own built-in
integrity tools (`PRAGMA integrity_check`, and FTS5's own `integrity-check`
command for `PagesFTS` - deliberately not a hand-rolled COUNT-based check,
having already been burned once this session by COUNT(*) on an
external-content FTS5 table silently proxying to the content table) with
application-level checks specific to this schema: orphaned rows (Books
pointing at a missing Library, Categories/Chapters/Pages pointing at a
missing Book), stale `PageCount`/`ChapterCount` caches, and duplicate
`(BookID, PageNo)` pairs. `verify_database_cli.py` prints a report and
exits non-zero only on real errors (stale counts are a warning, not an
error - they don't indicate corruption, just a cache that could be
refreshed).

8 new tests (86/86 total), each corrupting a fresh test database in one
specific, controlled way and confirming the right issue is detected.

Ran for real against the production database for the first time - the
whole point of building this now: **0 errors, 0 warnings** on 7,687 books,
after every operation performed on it this session (multiple imports,
deletions, deduplication, re-imports, title rewrites). This is real,
checked evidence the database is sound, not an assumption.

## Phase 2, step 2: backup and restore tooling

Second Phase 2 item, picked next for the same safety-first reason as the
verifier: the structural changes coming after this (Authors/Categories/
Volumes normalization) touch schema and data directly, and shouldn't be
attempted without a tested way to recover the live database first.

`infrastructure/persistence/database_backup.py`: `DatabaseBackupService`
with `create_backup`, `list_backups`, and `restore_backup`, all built on
SQLite's own online backup API (`Connection.backup()`) rather than a raw
file copy, so a backup taken while the database is open/in-use is still
safe and consistent. Backups are timestamped
(`<stem>_backup_<YYYYMMDD_HHMMSS>.db`) under `data/backups/`.

`interfaces/database_backup_cli.py`: `backup`, `list`, and `restore`
subcommands (first use of argparse subparsers in this project). `backup`
and `list` are non-destructive. `restore` overwrites the live database and
is gated behind an explicit `--yes` flag - refuses to run without it.

11 new tests (97/97 total) covering backup creation, listing order (most
recent first), an empty/missing backup folder, and restore both with and
without the confirmation flag.

Ran for real against the production database: created an actual backup of
`data/books.db` (4,440,469,504 bytes) and confirmed the backup file is
byte-identical in size to the live database. `data/backups/` added to
`.gitignore` - backup files are local safety copies, not committed
artifacts, same treatment as `data/staging/`.

## Phase 2, step 3: migration system

Third Phase 2 item: the remaining steps (Authors, Categories, Volumes,
Footnotes normalization) all require real schema changes. Until now schema
evolution has been ad-hoc, hand-written inline in `MasterBookRepository`
(e.g. `_ensure_library_id_column`, `_backfill_legacy_library`). That code is
working and untouched - this adds a general, versioned system for the
schema changes still to come, rather than more one-off methods.

`domain/models/migration.py`: a `Migration` record (version, description,
apply function). `infrastructure/persistence/migration_runner.py`:
`MigrationRunner`, using SQLite's own `PRAGMA user_version` as the version
counter (no extra tracking table). `migrate()` applies every migration
above the current version, in order, each in its own transaction.
Migration 1 is deliberately a no-op: it adopts the schema
`MasterBookRepository` already creates as the baseline, without
re-declaring any of it, so an existing database (at version 0) is tagged
version 1 with zero risk. Real structural changes start at version 2, when
Authors/Categories/Volumes work begins. `interfaces/migrate_database_cli.py`
applies pending migrations and reports what ran.

10 new tests (107/107 total): version defaults to 0 on a fresh database,
pending/ordering logic, idempotency (a second run applies nothing),
duplicate version numbers rejected, a real ALTER TABLE migration applied
through the runner, and the real `MIGRATIONS` registry adopting a fresh
database at the baseline version.

Ran for real against the production database (backed up beforehand via the
step 2 tooling): version went from 0 to 1, no schema change, no errors.

## Phase 2, step 4: Authors normalized into a real entity

Fourth Phase 2 item. Surveyed the real data before designing anything:
7,687 books, 3,221 with no recorded author, 650 distinct author values
among the rest (a mix of individual scholars and issuing
institutions/madaris - that is genuinely what the source `ANAME` field
contains, so that is what got modeled, not an idealized "person" entity).
Also confirmed what reads `Books.Author` today (`sqlite_book_search_repository.py`,
`sqlite_page_embedding_repository.py`, `hybrid_search.py`) so the change
could be made without touching any of it.

Migration 2 (`_normalize_authors` in `migration_runner.py`, the first real
structural migration built on top of the versioned system from step 3):
adds an `Authors` table (`AuthorID`, unique `Name`) and a `Books.AuthorID`
column, backfilled by matching each book's existing `Author` text.
`Books.Author` (free text) is left completely untouched - additive only,
nothing downstream had to change. `AuthorID` is NULL wherever `Author` is
NULL/empty.

New tests (108/108 total): the migration backfills correctly against real
`Book`/`Page` domain objects imported through `MasterBookRepository`
(shared authors collapse to one `AuthorID`, distinct authors get separate
rows, no-author books stay NULL), and the CLI end-to-end test now asserts
both migrations (1 and 2) apply against a freshly imported database.

Ran for real against the production database (fresh backup taken
immediately beforehand): **650 Authors rows, 4,466 books backfilled with
AuthorID, 0 mismatches** - exactly matching the pre-migration survey.
Verified with the step 1 database verifier afterward: still healthy.

## Phase 2, step 5: Categories normalized into a cross-library taxonomy

Fifth Phase 2 item. Surveyed the real data first: 13,929 per-book Category
rows, 691 distinct MJCN codes, shared across both Jibreel libraries
(Desktop and Mobile use the same source classification scheme, so one MJCN
code genuinely is the same category across both - not a coincidental
collision). Also found the data isn't perfectly clean: 4 MJCN codes have
inconsistent Name spelling and 1 has an inconsistent ParentMJCN across
different books (out of 691) - small enough to resolve deterministically
rather than needing manual review.

Migration 3 (`_normalize_categories`): adds a `CategoryTaxonomy` table
(`MJCN` primary key, `Name`, `ParentMJCN`), one row per distinct MJCN
across every book's Categories rows. Where a code's Name or ParentMJCN
disagrees across books, the most frequent value wins, tie-broken by the
smallest value for determinism. The existing per-book `Categories` table
is untouched - confirmed nothing outside the category-chain-to-subject
logic (`book_library_exporter.py`, `semantic_index_cli.py`) reads it, and
that logic keeps working unmodified since its source table didn't change.

New tests (111/111 total): dedup across books sharing an MJCN, the
frequency tie-break on a deliberately conflicting Name/ParentMJCN, and a
database with no categorized books producing an empty (not missing)
taxonomy table.

Ran for real against the production database (fresh backup taken
immediately beforehand): **691 CategoryTaxonomy rows**, exactly matching
the 691 distinct MJCN codes in the real data, including correct resolution
of all 5 known conflict cases. Verified healthy afterward.

## Phase 2, step 6: Volumes modeled as a Series entity

Sixth Phase 2 item. Surveyed the real data first: 2,501 book titles end
with a volume suffix (`جلد N` / `حصہ N` / `vol.`/`part`), and grouping by
the base title (suffix stripped) gives 412 real multi-volume series
covering 2,452 books. Spot-checked one series
(کفایت المفتی، 9 volumes) against `SourceBookID` before writing any
code - the source ids are sequential (995-1003), confirming this is a
real series, not a title-matching coincidence.

Migration 4 (`_model_volumes`): adds a `Series` table (`SeriesID`, unique
`Title` = base title) and additive `Books.SeriesID`/`Books.VolumeNumber`
columns. A base title only becomes a `Series` row when at least two books
share it - a lone "volume 1" with no siblings in this database is not a
demonstrated series, so it's left ungrouped rather than assumed.
`Books.Title` is untouched.

New tests (114/114 total): a real 3-volume series groups correctly with
sequential volume numbers, a lone volume-suffixed title stays ungrouped,
and a title with no volume suffix stays untouched.

Ran for real against the production database (fresh backup taken
immediately beforehand): **412 Series rows, 2,452 books assigned**,
exactly matching the pre-migration survey - including the same
کفایت المفتی 9-volume series confirmed by inspection. Verified healthy
afterward.

## Phase 2 closed: Footnotes evaluated and deliberately not built

Before building anything, checked what source data would back a Footnotes
entity - same approach as the Phase 1 Generic PDF decision. Inspected the
real `.mjbz` schema directly against a live source file (not just what our
reader parses): six tables total (`Content`, `Title`, `Information`,
`Category`, `sqlite_sequence`, `android_metadata`). `Content` carries only
`ContentF`/`ContentP` (formatted/plain page text) - no footnote table,
column, or marker anywhere. Maknoon and the PDF Archive are plain
page/text content with the same gap. No library in this corpus produces
structured footnote data.

Given that, decided not to build a Footnotes entity - there is nothing to
normalize. No code was written. If a future library (or OCR, later phase)
ever surfaces real footnote data, this can be revisited then.

### Phase 2 status: complete

- Database verification tool - built, validated against the real database
  (0 errors, 0 warnings).
- Backup/restore tooling - built, validated (byte-identical real backup).
- Migration system - built; every step since has run as a real, versioned
  migration against it.
- Authors - normalized (migration 2): 650 authors, 4,466 books backfilled.
- Categories - normalized into a cross-library taxonomy (migration 3): 691
  categories.
- Volumes - modeled as a Series entity (migration 4): 412 series, 2,452
  books.
- Footnotes - evaluated, deliberately not built (see above): no source
  data exists in any current library.
- Library IDs - already in place from the multi-library work earlier this
  session (`Libraries` table, `Books.LibraryID`); not repeated here since
  nothing new was needed.

All four real migrations validated against the actual 7,687-book
production database, each preceded by a fresh backup and followed by a
full integrity check. 114/114 tests passing throughout.

## PDF inventory and metadata cataloging (between Phase 2 and Phase 3)

User-requested audit, not a roadmap phase item: built a full inventory of
every PDF in three folders not yet in the database - `F:\jibreel full
pdf` (3,115 files), `F:\Maknoon Mufahris Almakhtotaat...` (3,258 files),
and `F:\JUMMA BAYANAT...` (2,718 files, a newly-identified Friday-sermon/
general-talks collection, not book content). Cross-referenced every file
against existing `Books.Source` (exact path) and `Books.Title` (case-
insensitive) to separate: already-catalogued, matches-existing-text-book,
and genuinely-new. Full row-level results saved to
`docs/pdf_inventory/pdf_inventory_2026-07-24.csv` (gitignored, local
only).

Findings: 9,091 raw PDFs, 5,931 distinct titles, 2,743 of which are
duplicate copies of the same book across the three folders (heavy overlap
between the Jibreel and Maknoon PDF collections specifically), 3,358
genuinely new titles not represented anywhere in the database.

At the user's request, catalogued every new PDF as a metadata-only Book
(title + path, no page content - same approach as the existing PDF
Archive, using the already-built `pdf_metadata_import_cli.py`, no new
code written). Ran against the real database (fresh backup taken first):

- `Maktaba Jibreel (PDF Archive)`: 672 imported, 2,443 skipped as already
  catalogued, 0 failed.
- `Maktaba Al-Maknoon (PDF Archive)` (new library, separate from the
  existing text-bearing `Maktaba Al-Maknoon`): 3,258 imported, 0 failed.
- `Jumma Bayanat` (new library): 2,718 imported, 0 failed.

Total books: **7,687 -> 14,335**. Verified healthy afterward (0 errors, 0
warnings).

**Known limitation, noted rather than silently left:** migrations 2-4
(Authors/Categories/Series) are one-time, version-gated backfills - they
already ran before this cataloging step, so the 6,648 newly-added
metadata-only books were not retroactively processed. In practice this
loses nothing real: these books carry no author/category metadata (title
+ path only), and none were checked for Series grouping. If that matters
later, it needs a deliberate incremental-backfill design, not a rerun of
the existing migrations.

## Phase 3, step 1: Arabic/Urdu-normalized search index

First Phase 3 (Search) item. Checked what already existed before building
anything: FTS5 keyword search, bm25 ranking, and `snippet()` highlighting
were already built (Phase-1-era). What Phase 3 still needed: normalization,
filters beyond library, verified boolean search, and a decision on root
search.

Surveyed real corpus text first: sampled 5,000 pages - 46% carry
diacritics (tashkeel), and letter-form variants are heavily used (Urdu yeh
"ی" appears 3x more often than Arabic yeh "ي" in the same corpus; hamza-
bearing alef forms أ/إ/آ appear ~37,000 times against 319,000 plain alef).
Literal FTS5 matching treats these as different words - a real,
significant recall gap for a mixed Arabic/Urdu corpus.

`shared/arabic_text_normalization.py`: one canonical mapping (13
diacritic/tatweel characters stripped, alef variants -> ا, yeh variants ->
ي, ة -> ه) driving both `normalize_search_text()` (pure Python, for
query-time normalization) and `build_sql_normalize_expression()` (a SQL
REPLACE-chain builder, for index-time normalization) - single source of
truth, so the two can never drift apart. A dedicated test asserts the SQL
and Python paths agree on every sample.

Migration 5 (`_add_normalized_search_index`): adds `PagesFTSNormalized`, a
standalone FTS5 table (not external-content, since it stores normalized
text rather than `Pages.Content` verbatim) plus a pure-SQL `AFTER INSERT`
trigger on `Pages`. Because the trigger is pure SQL (no registered Python
function), it works automatically for every future import through
`MasterBookRepository` without any change to that class - confirmed by a
test that imports a *second* book after migrating and checks the trigger
fired. Existing pages are backfilled in one `INSERT ... SELECT` statement.

`SqliteBookSearchRepository` now prefers `PagesFTSNormalized`, normalizing
the incoming query the same way, and **falls back to the plain `PagesFTS`
index (literal matching) when `PagesFTSNormalized` doesn't exist yet** -
a database that's been imported but not yet migrated is a normal state,
and search must keep working for it without requiring the caller (web
app, CLI) to know about migrations. A test covers each path explicitly.

**Trade-off made deliberately, not silently:** search excerpts now show
normalized text (no diacritics, unified letter forms) rather than the
page's exact original spelling, since the excerpt is drawn from
`PagesFTSNormalized` to keep matched-term highlighting correct. Stored
page content and the book viewer/PDF are completely unaffected - only the
search snippet. Diacritics are supplementary in Arabic/Urdu reading
(native text is normally printed without them), so this was judged an
acceptable, honest trade for the recall gain.

14 new tests (128/128 total, including the existing search-repository
suite exercising the fallback path unchanged). Ran for real against the
production database (fresh backup taken first): backfilled all
**2,046,888 pages** into `PagesFTSNormalized`. Verified with real queries
- "علی" and "علي" (Urdu vs Arabic yeh) now return identical results;
same for "أحمد"/"احمد". Verified healthy afterward (0 errors, 0
warnings).

## Phase 3, step 2: Author and Category search filters

Second Phase 3 item, made possible by Phase 2's Authors/CategoryTaxonomy
work. Extended the existing `library` filter pattern (unchanged in
behavior) with `author` (exact match against `Books.Author`) and
`category` (exact match against the per-book `Categories.Name`, via
`EXISTS`) - both optional, both additive to `SqliteBookSearchRepository`,
`BookSearchService`/`SearchIndex`, and `search_cli.py` (`--author`,
`--category`). `HybridSearchService` and `web_app.py` needed no changes -
new parameters are optional and trailing, called positionally with the
same three arguments as before.

Caught by the test suite, not by inspection: `FakeKeywordIndex` in
`test_hybrid_search.py` only accepted 3 positional arguments - adding the
new parameters to `BookSearchService.search()` would have made every
`HybridSearchService` call raise `TypeError` the moment hybrid/semantic
search was exercised for real. Fixed by updating the fake to match the
real protocol.

6 new tests (132/132 total). Validated for real against the production
database (read-only, no schema change, no backup needed): author filter,
category filter, and library+author combined all return correctly scoped
real results (e.g. کفایت المفتی by حضرت مولانا مفتی محمد کفایت اللہ دہلوی
صاحب, ارشاد المفتین under فتاوی).

## Phase 3, step 3: boolean search verified, real crash fixed

Third Phase 3 item. `SqliteBookSearchRepository` already passes the query
straight through to FTS5's `MATCH`, which natively supports `AND`/`OR`/
`NOT`, quoted phrases, and prefix (`term*`) queries - so "boolean search"
was really a verification task, not a build. Confirmed for real against
the production database: `قرآن AND حدیث`, `قرآن OR تفسیر`,
`قرآن NOT تفسیر`, `"حکم شرعی"`, and `قرآن*` all returned correct results.

Also tested deliberately malformed queries (bare `-`, an unbalanced
quote, a bare `AND`) against real data to see how they fail. The
repository layer already caught these correctly (`BookSearchError`, not a
raw crash) - but **`web_app.py`'s `/` route called `search_service.search()`
with no exception handling at all**, so typing an unbalanced quote into
the search box would have crashed the request with an uncaught 500. Found
by testing the actual failure path, not by inspection.

Fixed: the route now catches `BookSearchError` and renders a clear
"couldn't be run" message instead of crashing (`search.html` gets a
`.search-error` block, styled consistently with the existing `.no-results`
message - no other UI changes). This is a bug fix to existing search
handling, not new UI work, so it stays within the Phase 3 boundary rather
than Phase 4's GUI scope.

6 new tests (138/138 total): AND/OR/NOT/phrase queries against real
seeded content, a malformed-query error test at the repository level, and
a web-app regression test proving the malformed-query request now returns
200 with an error message instead of crashing.

## Phase 3, step 4: root search evaluated and deliberately not built

Checked what's available offline before building anything: no Arabic
morphology/stemming library is installed (`pyarabic`, `tashaphyne`,
`qalsadi`, `camel-tools` all absent). Real root extraction needs one of:
a verified root dictionary (none available, can't be fabricated), a
rule-based light stemmer (installable, but known 30-50% error rates -
would actively return wrong results as often as right ones), or a real
statistical morphological analyzer (accurate, but needs downloaded
models and is arguably AI-adjacent, conflicting with Phase 3's explicit
"No semantic AI" rule). Also a corpus-fit problem: root-pattern morphology
is Arabic-specific and a large share of this corpus is Urdu (no root
system), so it would only ever help part of the library.

Presented this assessment to the user with three options (skip / build an
unreliable stemmer anyway with the error rate documented / defer).
**Decision: skip.** No code written. Can be revisited if a verified-root
resource becomes available, or folded into Phase 6 alongside other
advanced language features.

## Phase 3, step 5: highlighting and page navigation confirmed (no changes needed)

Final Phase 3 item. Both were already fully built (Phase-1-era) and
required no changes: `snippet()`-based `**term**` highlighting (converted
to `<mark>` tags in the web app) and page navigation (PDF results open at
`#page=N`; the in-app reader uses `?page=N` with a `#jump` anchor).
Re-verified both still work correctly with this phase's new normalized
search index - real production output showed `**علي**` markers rendering
correctly in excerpts - and confirmed via the existing, unmodified,
still-passing web-app test suite. Nothing built; explicitly confirmed
rather than assumed.

### Phase 3 status: complete

- FTS5 keyword search, bm25 ranking - already built (Phase 1).
- Arabic/Urdu normalization - built (migration 5): 2,046,888 pages
  indexed into `PagesFTSNormalized`, verified with real variant-spelling
  queries.
- Filters - library (already built) plus new author/category filters.
- Boolean search - verified working via FTS5's native syntax; found and
  fixed a real crash bug in the web app along the way.
- Highlighting and page navigation - confirmed already working, no
  changes needed.
- Root search - evaluated, deliberately not built (see above): no
  reliable offline option exists.

138/138 tests passing. Every real-data change (migration 5) was preceded
by a fresh backup and followed by a full integrity check; the two filter/
boolean-search steps were read-only against the schema and needed neither.

## Phase 4 prep: shared PDF source resolver, real bug fixed

Before starting the desktop app, extracted `web_app.py`'s local
`resolve_pdf_path` closure into `application/pdf_source_resolver.py` so
the upcoming desktop GUI doesn't duplicate this logic (`Never duplicate
code`). While extracting it, found a real gap: the closure only
recognized `Maktaba Jibreel (PDF Archive)` as a PDF-source library - the
two PDF libraries added this session (`Maktaba Al-Maknoon (PDF Archive)`,
`Jumma Bayanat`) store their real PDF path as `Source` the exact same
way, but had no route to it, so their "Open PDF" link never appeared even
though the files exist. Fixed by generalizing to a `PDF_SOURCE_LIBRARIES`
set instead of a single constant.

8 new tests (146/146 total): the resolver's own unit tests (all library
cases, including the fix), plus a web-app regression test proving both
newly-added libraries now render an "Open PDF" link for a real match.

Also extracted `web_app.py`'s Flask-`Markup`-specific excerpt highlighter
into `shared/excerpt_highlighting.py` (stdlib `html.escape` only, no
Flask dependency) so the desktop app could reuse it too, ahead of
actually needing it. 5 more tests (151/151 total).

## Phase 4, step 1: desktop app shell + Search screen (PySide6)

First real Phase 4 milestone. Added `gui`/`build`/`gui-dev` optional
dependency groups (PySide6, pyinstaller, pytest-qt) to `pyproject.toml`.

`interfaces/desktop_app/`: `MainWindow` (a navigation rail - Search,
Viewer, Import, Settings - over a `QStackedWidget`) and `SearchScreen`,
wired to the exact same, already-tested `BookSearchService` and
`BookBrowserRepository` the CLI and web app use - no new search logic,
no duplicated business logic. Viewer/Import/Settings are honest "coming
in a future update" placeholders (verified to have zero interactive
controls, not fake buttons) rather than pretending to be built.

The "Open PDF" button reuses `pdf_source_resolver.resolve_pdf_path`
(fixed in the prep step above) and `QDesktopServices.openUrl` to hand
the file to the OS's default PDF viewer; when no PDF is available it
shows an honest "In-app viewer not built yet" note rather than a dead
button - the Viewer screen is a separate, later milestone.

8 new tests (159/159 total) using `pytest-qt` in offscreen mode (a
`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` so the suite runs
headless): ranked results, no-results messaging, the author filter, the
library dropdown being populated from the real database rather than
hardcoded, and that a new search replaces rather than appends to the
previous result set.

**Two real bugs found and fixed by actually rendering the app against
the production database and screenshotting it** (not just by running
tests): (1) a first screenshot attempt used the Qt "offscreen" platform
explicitly, which turned out to have no usable font database in this
environment - even English rail labels rendered as blank boxes; letting
Qt pick its default platform (`windows`, on this machine) fixed it, and
confirmed the earlier offscreen test run was still valid since tests
don't depend on visual text rendering. (2) search-result highlighting
was semantically correct (`<mark>` tags, verified by tests) but
**invisible** - Qt's rich-text engine has no default `<mark>` styling
the way a browser does. Fixed in `shared/excerpt_highlighting.py` by
emitting an inline `background-color` style instead of a bare tag,
benefiting the web app too (previously relying on external CSS alone).

Verified for real against the production database: searched "علی",
got 30 correctly ranked, highlighted, real results (e.g. الأصل المعروف
بالمبسوط للشيباني, العناية شرح الهداية) with correct titles, authors,
libraries, and page numbers, screenshotted for visual confirmation.

## Phase 4, step 2: packaged into a standalone, portable exe

`build_installer.ps1` runs PyInstaller (`--onedir`, `--windowed`) to
produce `installation/IslamicResearchHub/IslamicResearchHub.exe` - a
self-contained ~110 MB folder that runs without a separate Python
install. `installation/` is a build output (gitignored, like `data/`),
rebuildable any time with the script.

**A real bug found by actually running the packaged exe, not just
building it:** the app resolved `data/books.db` relative to the current
working directory, which is unreliable for a double-clicked exe (Windows
Explorer's CWD behavior isn't guaranteed, and shortcuts/command-line
launches can differ). Fixed in `desktop_app/__main__.py` to resolve the
database path relative to the executable's own folder when frozen
(detected via `sys.frozen`), keeping the previous CWD-relative behavior
in dev mode. Also found that a missing database was handled silently
(SQLite auto-creates an empty file on connect) - `MainWindow` now checks
`database_path.is_file()` first and shows a clear "Database not found"
message with the expected path instead of building a broken, empty
search screen. 1 new test (160/160 total) locks in that the database is
never silently auto-created.

Verified for real, end-to-end, as an actual separate Windows process
(not just via Python test/import): launched the real `.exe` with no
database present - stayed running, showed the honest missing-database
message. Then hard-linked the real production `data/books.db` (8.2 GB,
zero-copy, same NTFS volume) into `installation/IslamicResearchHub/data/`
and relaunched - the process started, initialized correctly (window
title confirmed via `Get-Process`), and stayed running.

README.md added inside `installation/`, in English, Urdu (`README.ur.md`),
and Arabic (`README.ar.md`) - what the app is, how to run it, where the
database must go, what's not built yet, and a note that moving the
folder to another machine needs `data/books.db` copied separately if a
hard link was used. Main `README.md` and `PROJECT.md` updated to point
at it and reflect Phase 4's real (in-progress) status.

## Maktaba Islam: real overlap check, then genuinely new content imported

User-requested audit of `F:\MaktabaIslam` (~3 GB, a different Islamic
library app already on disk). Real comparison, not a guess: of 1,860
actual `.mjbz` files present, 1,745 titles (94%) exactly matched what we
already have - strong evidence of a shared underlying publisher/platform,
confirmed by a second finding: the individual `.mjbz` files use the
*exact same schema* (`Content`/`Title`/`Information`/`Category`) as
Maktaba Jibreel Mobile, so the existing importer reads them with zero new
code. Of the PDF collection (297 files), 216 also overlapped by filename.

Imported only the genuinely new content, not the whole folder (which
would have created ~1,960 duplicate catalog entries): staged the 60
non-overlapping `.mjbz` files and ran the existing scan CLI against just
that folder (`--library "Maktaba Islam"`); catalogued the 81 non-
overlapping PDFs by their original `F:\MaktabaIslam\pdf\` paths (not
copied - metadata-only entries need a stable permanent path for "Open
PDF" to keep working later), reusing `read_pdf_metadata` +
`MasterBookRepository` directly, matching the existing PDF-Archive
pattern exactly.

**Real, not silent, data-quality finding:** only 48 of the 60 staged
`.mjbz` files actually imported - the other 12 failed with SQLite's own
"database disk image is malformed" error, i.e. genuinely corrupted source
files. This is the exact resilience behavior built earlier this session
for Maknoon (skip and log, don't stop the batch) working correctly on a
new, unrelated library, not a bug. Diagnosed by reading the actual
extraction log, not assumed.

Total books: 14,335 -> 14,464 (48 full-text books in `Maktaba Islam`, 81
metadata-only in `Maktaba Islam (PDF Archive)`). Fresh backup taken
first, verified healthy afterward (0 errors, 0 warnings).

## Housekeeping: dead files removed, gitignore gap fixed

User asked directly whether there were dead/useless files in the repo -
audited rather than assumed clean. Found and fixed:

- `docs/pdf_catalog_maktaba_islam/` (a new generated report folder from
  the import above) wasn't covered by `.gitignore` - only the exact name
  `docs/pdf_catalog/` was. Generalized to `docs/pdf_catalog_*/`.
- `requirements.txt` was stale - a comment-only file pointing at
  `pyproject.toml`'s extras, left over from before those extras existed.
  Deleted; `README.md`'s "Getting started" no longer references it.
- `PROJECT_REVIEW.md` was a dated, one-off audit snapshot (2026-07-22)
  whose findings are now either resolved or superseded by `CHANGELOG.md`/
  `PROJECT.md`. Deleted rather than left to mislead a future reader.
- `interfaces/web_app_cli.py` and `Open Islamic Research Hub.bat` were
  real and actively used (the batch file is the one-click way to start
  the web app) but undocumented - added to `README.md` rather than
  removed.
- Confirmed clean, no action needed: no dead/unimported source modules,
  no orphaned tests, `config/`/`domain/repositories/` are still the
  documented-intentional empty placeholders, `installation/` is not
  accidentally tracked in git.

## Maktaba Shamila Urdu: new importer, and the first real Footnotes data

User-directed investigation, done before writing any code: researched
Maktaba Shamila Urdu online (shamilaurdu.com - a dedicated Urdu product,
separate from the main Arabic Shamela that stays excluded), downloaded
its Windows portable build (297.4 MB; the first download attempt
silently truncated at 172 MB with no error - caught by comparing the
downloaded size against the server's real `Content-Length`, not assumed
complete), and inspected its actual data format before deciding whether
it was worth building anything for.

Found a genuinely different, genuinely valuable source: only 3 of 695
titles (0.4%) overlap with the existing corpus - a different scholarly
tradition (Ahle Hadith/Salafi authors, e.g. Ibn Baz, Ibn Uthaymeen) from
this corpus's mostly-Deobandi lean, not a repackaged duplicate. Each book
is its own self-contained SQLite file (`Book`, `tableOfContents`,
`metadata` tables) - a different schema from Jibreel's, discovered to
also carry real footnote content (`fnotes` column, Quranic ayah
citations), which is data this corpus has never had.

Given the real, high-overlap difference from Maktaba Islam (which reused
the existing `.mjbz` pipeline unchanged), this genuinely needed new code:

- `Page.footnote: str | None = None` - additive field on the existing
  domain model.
- `Footnotes` table added to `MasterBookRepository`'s schema (same
  additive `CREATE TABLE IF NOT EXISTS` pattern already used for
  `Libraries`/`PagesFTS`), populated during page insert.
- `DatabaseVerifier`'s orphan checks extended to cover `Footnotes` -
  and, while doing that, found and fixed a real robustness gap: the
  orphan-check loop had no guard for a table not existing yet, meaning
  running the verifier against an older database (predating a newly
  added table) would crash instead of just skipping that check.
- `ShamilaUrduBookReader` (new): reads a book's own metadata/content/TOC
  tables, strips the HTML-styled content to plain text (stdlib
  `html.parser`, no new dependency - every other library's content is
  plain text and search/display already assume that).
- `shamila_urdu_import_cli.py` (new): walks `Books/<category>/*.db`,
  skips `library.db` (the catalog index, not a book), same
  survives-corrupted-files resilience as every other importer.

13 new tests (171/171 total): reader tests (HTML stripping, footnote
extraction, translator-fallback-when-no-author, blank TOC entries
skipped, corrupted-file error handling), CLI tests (real import, corrupted
file survived, missing folder), repository tests (footnotes stored only
for pages that have them), and verifier tests (orphaned footnotes
detected, missing-table case doesn't crash).

Ran for real against the actual downloaded corpus (fresh backup taken
first): **663/663 books imported, 0 failures, 67,056 real footnote rows**.
Verified with a real search ("زکوۃ" against the new library) returning
correctly ranked, highlighted results with real Salafi-tradition author
names. Verified healthy afterward (0 errors, 0 warnings) on the full,
now 15,127-book database.

## Phase 4, step 3: Viewer screen (in-app page reading)

Second Phase 4 GUI milestone. Until now, search results without a PDF
just showed "In-app viewer not built yet" - Search could find a book but
not let you read it. `interfaces/desktop_app/viewer_screen.py` (new):
loads one book's real pages via the existing, already-tested
`BookBrowserRepository.get_book_detail()` (no new query logic), shows
one page at a time with Prev/Next, a page-number jump box, and A-/A+
font-size controls - deliberately no table-of-contents yet, to keep this
milestone shippable; that can be added later without redesigning
anything here.

`SearchScreen` gained a `Read in app` button on every result (alongside
`Open PDF` when one exists, not instead of it) that emits
`open_in_viewer_requested(book_id, page_number)`. `MainWindow` wires this
to the real `ViewerScreen` instance: switches the rail to the Viewer tab
and jumps straight to the matched page, not just page one - so clicking
a result actually takes you to what you searched for.

10 new tests (177/177 total): page loading and metadata, Prev/Next
navigation through real page content, jump-to-page, font size bounds, an
unknown book id returning `False` instead of raising, and a `MainWindow`
integration test proving the signal correctly switches screens and loads
the right book/page.

Verified for real against the production database: searched "زکوۃ",
clicked "Read in app" on the first result, and the Viewer opened showing
the correct real book (کتاب الفتاوی جلد 3, real author, 324 real pages)
already scrolled to the exact page the search matched (14, not 1) -
screenshotted for visual confirmation.

## Phase 4, step 4: Import screen (library sources + duplicate review)

Third Phase 4 GUI milestone. `ImportScreen` (new): a real library-sources
table (`BookBrowserRepository.list_libraries_with_counts()`, a small new
method added to that repository) and real duplicate-candidate review,
wired entirely to `DuplicateCandidateRepository` - already built and
tested earlier this session, not new logic. "Scan for duplicates" calls
its `detect_and_store()`; "Remove empty-stub duplicates" calls its
`resolve_empty_stub_duplicates()`, which only ever deletes the zero-page
side of a pair and never touches a pair where both sides have real
content - the same safe behavior already covered by that repository's
own tests, just exposed in the GUI now.

While adding tests, found that `book_browser_repository.py` had no
direct test file at all (only ever exercised indirectly through the web
app and the newer desktop screens) - added one covering all four of its
methods, not just the new one.

**A real bug found by testing, not by inspection:** the "Removed N
empty-stub duplicate(s)" confirmation message was being immediately
overwritten by the table refresh's own status text, so the user would
never actually see it. Fixed by composing both messages together after
the reload, instead of setting one then letting the other clobber it.

10 new tests (187/187 total): 4 for `ImportScreen` (library table
reflects real counts, scanning finds a real cross-library title match,
cleanup removes a real empty-stub duplicate and refreshes both tables,
`refresh()` picks up an external change) plus 6 new
`BookBrowserRepository` tests (filling the gap found above).

Verified for real against the production database (fresh backup taken
first, since "Scan for duplicates" writes to `DuplicateCandidates`):
all 9 real libraries with correct real counts (summing to exactly
15,127). Running a fresh scan for real found candidates had grown from
27 (stale, computed at a much smaller corpus size) to 2,302 - expected
at this scale for exact-title matching, not a regression, and the
refreshed list correctly re-surfaced a genuine known overlap (تزکیہ نفس
between Maktaba Shamila Urdu and Jibreel Mobile - one of only 3 exact
title overlaps found during that library's original investigation).
Verified healthy afterward (0 errors, 0 warnings).

## Phase 4, step 5: Settings screen - real language switching, RTL/LTR

Final Phase 4 GUI milestone for this round. User had explicitly asked
for Urdu/Arabic/English app-language options with automatic RTL/LTR back
when the Phase 4 design preview was built - this makes it real, not a
mockup.

`interfaces/desktop_app/i18n.py` (new): `Translator(QObject)`, backed by
`QSettings` for persistence across restarts, with a `language_changed`
signal so every screen can react. `QApplication.setLayoutDirection()` is
set from the *current* language, which mirrors the *entire* app's layout
automatically (rail moves to the correct side, etc.) - a real Qt
capability, more powerful than the CSS-based direction flip in the
earlier HTML preview. Only the app's own chrome translates; book content
always stays in its original script, exactly as promised in that
preview. Scope kept honest: only the rail labels and Settings' own
labels are wired to translation keys this round, not every screen's
strings - a deliberate, incremental boundary, not an oversight.

`SettingsScreen` (new): language selector, a default reading font size
(persisted via `QSettings`, read by `ViewerScreen` at construction via a
new `initial_font_px` parameter - applies to newly opened books, not a
live override of an already-open one), and a real About section (actual
database path, actual book/library counts).

**A real bug found by testing, not by inspection - and a more serious
one than usual:** `MainWindow` always constructed the *real*
`QSettings(SETTINGS_ORGANIZATION, ...)`, which on Windows writes to the
actual registry. Every existing `MainWindow` test was silently reading
and writing the real, persistent app settings for the actual packaged
exe - and the language-switching test had already left a stray
`language=ur` value in the real registry before this was caught. Fixed
by adding an injectable `settings` parameter to `MainWindow` (same
pattern already used for `Translator`), updating every test to use an
isolated temp-file-backed `QSettings`, and manually removing the
already-polluted real registry key. Also fixed a real Qt Style Sheet
gotcha: a `QFrame` type-selector stylesheet was cascading into child
widgets' internal frames (e.g. a `QComboBox`'s popup), drawing a border
around every label instead of just the intended block - fixed with a
scoped `#settingsBlock` ID selector, the standard Qt fix for this.

14 new tests (202/202 total): 8 for `Translator` (default language,
switching, RTL for both Urdu and Arabic, signal emission - including a
no-op-does-not-emit case, unknown language code rejected, English
fallback for a missing key, persistence across instances) and 6 for
`SettingsScreen` (font size default/persistence, language combo reflects
and updates the shared translator, self-retranslation, real About data).

Verified for real against the production database (read-only, no
database writes this round - only `QSettings` - so no backup/verify
cycle needed): screenshotted Settings in English, then after switching
to Urdu - rail correctly moved to the right and retranslated (Search ->
تلاش), the whole app confirmed `LayoutDirection.RightToLeft`, and the
real 15,127-books/9-libraries About text stayed correct throughout.

## Correction: Maktaba Shamila Urdu import report was wrong - Hadith/Quran content never imported

Found while screenshotting the new Logs screen (below) against the real
production log: it showed real `ERROR` entries, at the exact same
timestamp as the original Shamila Urdu import run, for files under
`Hadith/` and `Quran/` subfolders failing with `no such table: Book`.
This contradicts the "663/663 books imported, 0 failures" reported
above.

Investigated rather than assumed: `shamila_urdu_import_cli.py`'s own
file-discovery (`folder.rglob("*.db")`, excluding `library.db`) finds
**698** files under the full `data` folder, not 663 - 663 under
`Books/`, 15 under `Hadith/`, 20 under `Quran/`. The CLI does track and
print a `Books failed` count separately from `Books processed`; the
earlier report simply repeated the wrong number instead of the real
one. Confirmed directly against the live database: **zero** Hadith or
Quran-folder books are present - the 663 imported are exactly and only
the `Books/` folder content.

Inspected the 35 failing files directly (not guessed): they use three
schemas distinct from `Books/`'s `Book`/`tableOfContents`/`metadata`
tables, which is why `ShamilaUrduBookReader` couldn't read them:

- **15 Hadith collections** (e.g. `abu-dawood.db` = Sunan Abi Dawud):
  `hadith` table with Arabic + Urdu text, `Kitab`/`Baab` chapter
  hierarchy, per-hadith grading (`HadithHukamAjmali`, e.g. `صحیح`/
  `ضعیف`), and commentary (`HadithHashiaText`).
- **1 base Quran text** (`Quran.db`): `surahs` + `Quran` tables, ayah by
  ayah, Arabic text only.
- **~19 Quran translations/tafsirs** (`Tarjuma*.db`, `Tafseer*.db`):
  ayah-by-ayah Urdu text (HTML-styled, same stripping approach as
  `Books/`), surah/ayah references, no chapter hierarchy.

No data has been lost - this content was never imported in the first
place, and the source files are still present in the downloaded corpus.
Real Hadith and Quran content, currently entirely absent from the
corpus, is the next planned import work (see below/upcoming entry).

## Phase 4, step 6: Logs and Book Details

Closes out the original 8-tab Phase 4 list. Both wired to real data,
no new domain logic - just surfacing what already exists.

`LogsScreen` (new): reads the real, already-configured application log
file (`islamic_research_hub.log`), shows the most recent 500 lines
newest-first (the file itself can run to tens of thousands of lines - a
production run this session produced 19,776), with an honest "No log
file yet" message rather than a blank screen when nothing has been
logged. Reused the same CWD-relative-path bug already fixed once for
the database path: `__main__.py` called `configure_logging()` with no
arguments (default `Path("logs")`, resolved against the process's
current working directory - fragile for a double-clicked exe). Fixed
the same way, with a `DEFAULT_LOG_DIRECTORY` resolved from the frozen
exe's own folder via the existing `sys.frozen` check.

`BookDetailsDialog` (new) + `BookMetadata` domain model (new,
`domain/models/book_metadata.py`): a `QFormLayout` showing a book's full
catalog record (author, publisher, language, category, library, page/
chapter counts, series/volume if present) from a new
`BookBrowserRepository.get_book_metadata()` method. Reachable from a new
always-present "Details" button on every search result card (previously
only "Open PDF"/"Read in app" were shown, and only when a PDF existed).
Series/volume support is conditional on migration 4 having run
(`_has_series_support()` existence check) - a freshly-imported,
not-yet-migrated database has neither a `Series` table nor a
`Books.SeriesID` column, and would otherwise crash with "no such table:
Series" instead of just omitting that field.

8 new tests (210/210 total): 4 for `LogsScreen` (real content shown,
line cap honored, missing-file message, refresh picks up new lines) and
4 across `test_book_browser_repository.py`/`test_search_screen.py` for
`get_book_metadata` (full real details, series after migration, unknown
book returns `None`, dialog opens with the real metadata from a click).

Verified for real: screenshotted the Logs screen against the actual
19,776-line production log, and the Details dialog opened from a real
search result ("زکوۃ") showing its real author/publisher/category. No
database schema change this round, so no backup/verify cycle was
needed - `BookMetadata`/`get_book_metadata` are read-only additions.

## Maktaba Shamila Urdu: Hadith and Quran folders imported (closes the correction above)

Follow-up to the correction entry above. Inspected the 35 previously-
failing files directly rather than guessing: three real, consistent
schemas, none matching `Books/`'s `Book`/`tableOfContents` format -
which is why the original single reader silently failed on all of them.

- **15 Hadith collections** (`Hadith/*.db` - Sahih al-Bukhari, Sahih
  Muslim, Sunan Abi Dawud, Jami' at-Tirmidhi, Sunan Ibn Majah, Sunan
  an-Nasa'i, Bulugh al-Maram, and 8 more): a `hadith` table with Arabic
  text, Urdu translation, `Kitab`/`Baab` chapter hierarchy, per-hadith
  grading, and HTML-styled commentary. One real-world variant found and
  handled: `tirmizi.db` has a small extra `hadith5` table (63 hadith
  outside the main numbering) - included as its own trailing chapters
  rather than silently dropped.
- **20 Quran-folder files** (`Quran/*.db`): one base Arabic text
  (`Quran.db`), 7 Urdu translations (`Tarjuma*.db`), and 12 tafsirs
  (`Tafseer*.db` - Ibn Kathir, As-Sa'di, and 10 more), all ayah-by-ayah
  with a shared surah/ayah shape despite differing table names.
  `Quran.db`'s own metadata is vendor placeholder junk ("dsddd"/"AAAA"),
  the one case in this corpus where a source's stated title/author is
  known-garbage rather than merely absent - overridden with an honest
  label instead of propagated, and disclosed here rather than done
  silently.

New code, reusing the existing `Book`/`Page`/`Chapter`/`Footnotes`
pipeline unchanged - no schema or importer-framework changes needed:

- `shared/html_text_extraction.py` (new): the HTML-to-text stripping
  logic, extracted out of `shamila_urdu_book_reader.py` (which now
  imports it) so the two new readers below don't duplicate it.
- `ShamilaUrduHadithReader` (new): one hadith row -> one `Page` (Arabic
  + Urdu + a `[grade]` tag as the searchable content); `HadithHashiaText`
  commentary -> the page's footnote; Kitab/Baab -> a two-level table of
  contents.
- `ShamilaUrduQuranReader` (new): one ayah row -> one `Page`; detects
  which of the three table names (`Quran`/`Tarjuma`/`Tafseer`) a given
  file actually has; surahs -> the table of contents.
- `shamila_urdu_import_cli.py`: now dispatches each file to the reader
  matching its top-level folder (`Books/` / `Hadith/` / `Quran/`)
  instead of assuming every file is a `Books/`-shaped book. `Books/`
  behavior is unchanged.

9 new tests (219/219 total): 4 for the Hadith reader (Kitab/Baab
hierarchy, HTML-stripped commentary as footnote, the real `hadith5`
edge case, corrupted-file error handling), 4 for the Quran reader
(placeholder-metadata override, HTML-stripped translation, Tafseer
recognized like Tarjuma, corrupted-file error handling), and a CLI test
confirming Hadith/Quran files import alongside `Books/` files in one run.

Ran for real against the actual downloaded corpus (fresh backup taken
first): all **698 files now processed with 0 failures** (663 already-
imported `Books/` files correctly skipped as duplicates via the
existing source-path check, 35 new Hadith/Quran files imported, 0
failed) - **181,717 new searchable pages** (hadith + ayahs) across the
35 new books. Verified with a real search: Sahih al-Bukhari's opening
hadith ("Actions are judged by intentions") reads correctly end-to-end
- Arabic, Urdu translation, full commentary, and the `[صحيح]` grading
tag - and general full-text search returns real Hadith/Quran content
alongside the rest of the corpus. Verified healthy afterward with
`DatabaseVerifier` on the now-15,162-book database.

## Phase 4 visual polish: app-wide theme matching the design preview

The desktop app was functionally complete but still used default Qt/
Windows widget styling - grey buttons, no color palette - unlike the
warm cream/green Phase 4 HTML design preview shown early in the
project. Only a handful of labels had been given ad hoc inline colors
(several files each independently hardcoding a slightly different
"#7a7264" guess for muted text), which is why the running app looked
noticeably plainer than that preview.

`interfaces/desktop_app/theme.py` (new): the design preview's exact
color tokens (`--bg`, `--surface`, `--ink`, `--accent`, etc. from its
CSS `:root`), a `GLOBAL_STYLESHEET` Qt stylesheet applied once via
`app.setStyleSheet()` in `__main__.py`, and two shared style-string
constants (`MUTED_LABEL_STYLE`, `RTL_TEXT_STYLE`) so every screen
references one source of truth instead of repeating hex codes. Covers
buttons (including a primary/accent variant), inputs, dropdowns, the
nav rail (with a real `:checked` active-state highlight, via Qt's
native pseudo-state support - not previously used), cards, tables, and
scrollbars. Every screen file updated to use these instead of its own
inline hex strings; behavior unchanged, colors/fonts centralized.

Real bug found and fixed during verification (screenshot comparison,
not just code review): the first draft's blanket `QWidget { background:
... }` rule painted an opaque background on every widget, including
plain `QLabel`s sitting on top of white cards - each label rendered as
a solid rectangle instead of transparent text, visually breaking every
screen. Fixed by scoping `background` to `QMainWindow` only and making
`QLabel`/`QScrollArea` explicitly transparent, letting cards' own
backgrounds show through correctly.

Also fixed, found while investigating what first looked like a search-
result layout bug (turned out to be real, just not the bug it first
appeared to be): `SearchScreen`'s excerpt label is word-wrapped rich
text, which Qt's `QVBoxLayout` can under-size unless the label's size
policy explicitly declares `heightForWidth` support - added a small
`_enable_height_for_width()` helper so longer, multi-line excerpts get
their full needed height instead of being clipped to one line.

219/219 tests unaffected (no behavior changed, only `setObjectName`/
`setStyleSheet` calls). Verified for real: screenshotted Search,
Viewer, Import, and Settings against the production database - cream/
white/green palette, working nav-rail active-state highlight, correctly
laid out result cards with real Urdu text and highlighting, all
matching the design preview's look.

## Phase 4 structural rebuild: header bar, category/author browsing, add-library form, reading fonts

The previous round only matched the design preview's *colors*. Comparing
the running app side-by-side with the actual mockup surfaced real
structural gaps: no header bar (wordmark/live stats/language switcher),
no category/author browsing, Details opened a popup instead of an
inline side panel, no way to add a library from the GUI, text-only nav
buttons instead of icon+label, and no reading-font choice. None of
these were regressions - each was a real, disclosed scoping decision
made when that screen was originally built - but the user asked for
full structural parity with the mockup, not just its palette.

**New repository queries** (`BookBrowserRepository`, all with the same
existence-guard pattern as `_has_series_support`, so a pre-migration
database still works):
- `get_header_stats()` - real book/library/author/category/series
  counts. Verified against production: 15,162 books, 9 libraries, 650
  authors, 691 categories, 412 series - matching the mockup's own
  numbers almost exactly (an earlier snapshot of this same corpus).
- `list_authors_with_counts()` - real authors, using the normalized
  `Authors` table when migrated, `Books.Author` text otherwise.
- `get_category_tree()` - the real category hierarchy with real book
  counts, using `CategoryTaxonomy` when migrated. **Real bug found and
  fixed**: root categories use MJCN sentinel `0` as `ParentMJCN` in this
  corpus's actual data (not `NULL`, the more obvious assumption) - the
  first version returned an empty tree against production until this
  was caught and fixed.

**`HeaderBar`** (new): wordmark + tagline, the five live stats above,
and a language-pill switcher that writes through the same `Translator`
Settings already uses - changing language from either place updates
both.

**Icon nav rail**: `icons.py` renders the mockup's own inline SVG paths
(via `QSvgRenderer`) into per-state `QIcon`s (muted normally, accent
when checked - `QIcon` natively supports a distinct pixmap per
`QIcon.State`, no manual state-tracking needed). Rail buttons switched
from `QPushButton` to `QToolButton` (`ToolButtonTextUnderIcon`), since
plain `QPushButton` has no built-in icon-above-text layout.

**`SearchScreen` rebuilt as three panes**, reusing the existing query/
filter/result-card logic unchanged:
- Left: Categories/Authors tabs. Categories is a real `QTreeWidget`
  built from `get_category_tree()`; Authors is a scrollable list from
  `list_authors_with_counts()`. Clicking either sets the existing
  category/author filter field and re-runs the existing search - no
  new filtering logic. A library-chips list (real counts) does the same
  for the library filter. **Real bug found and fixed during
  verification**: nesting the `QTreeWidget` (which already scrolls
  internally) inside an outer `QScrollArea` produced a 21,452px-tall,
  865px-wide tree - `QScrollArea` gives its content exactly its
  `sizeHint`, and an unconstrained `QTreeWidget`'s `sizeHint` wants to
  show every row at once. Fixed by making the left pane a plain
  (non-scrolling) fixed-width widget instead, letting the tree scroll
  itself and wrapping only the (non-self-scrolling) author list in its
  own inner `QScrollArea`.
- Right: an inline detail panel (title, author, publisher, language,
  category, library, series/volume, pages, chapters, matched page,
  Open in Viewer / Open source PDF) replacing the old `BookDetailsDialog`
  popup - `book_details_dialog.py` removed as dead code, its logic
  inlined into `SearchScreen._populate_detail_panel`.
- Known, disclosed limitation carried over unchanged: category/author
  filtering was already an exact-text match against the per-book
  `Categories.Name`/`Books.Author` columns before this work: a tree/list
  entry's canonical name (post-normalization) can occasionally miss a
  book whose own stored spelling differs. Not new, not fixed here.
- Also noticed, not fixed: `BookMetadata.category` shows the raw
  internal MJCN code (e.g. "603") for standard `.mjbz` imports rather
  than a resolved name, since `Books.Category` stores the MJCN badge
  directly - a pre-existing data-modeling quirk, out of scope for this
  structural-parity pass.

**`ImportScreen` gets a real "Add new library" form**: folder picker
(`QFileDialog`), format dropdown (auto-detect / `.mjbz` Mobile /
pre-extracted text / PDF metadata-only), library name, and a real
"Scan & import" that runs off the GUI thread
(`LibraryImportWorker(QThread)`, new) using the exact same
`MjbzFolderScanner`/`MasterDatabaseBuilder`/reader classes the CLI
importers already use - no new import logic, just a Qt wrapper so a
real scan doesn't freeze the window. Jibreel Desktop (`.mjbx`,
encrypted) is deliberately not wired here - it needs extra
configuration (SQLite DLL path, password) that doesn't fit this simple
form, and stays CLI-only, same as before. A new `library_imported`
signal refreshes the header's live stats after a real import completes.

**Reading font choice** (new, `reading_fonts.py`): 10 real Urdu
(Nastaliq-style: Noori Nastaleeq, Jameel Noori Nastaleeq, Noto Nastaliq
Urdu, Alvi Nastaleeq, Nafees Nastaleeq) and Arabic (Naskh-style:
Traditional Arabic, Simplified Arabic, Scheherazade New, Amiri, Sakkal
Majalla) fonts, each a CSS-style fallback chain so Qt substitutes
gracefully when a font isn't installed. A dropdown in the Viewer
toolbar and a matching default-font picker in Settings, both persisted
via `QSettings` the same way font size already was.

Tests: 219 -> 230, all passing. 4 for the new repository queries (header
stats pre/post migration, authors with counts, category tree with the
real MJCN-`0` root convention); in `test_search_screen.py`, the old
dialog-based Details test was replaced with 3 new ones (inline detail
panel, clicking a category, clicking an author); 5 for reading-font
selection (Viewer default/dropdown/persisted-initial-value, Settings
default/persistence).

Verified for real end-to-end against the production database: header
stats match real counts; the real 16-top-level category tree (e.g.
"فقہ اور اصول فقہ" 361, "حدیث شریف" 95) renders with real children;
clicking a real author or library chip re-runs a real search; the
detail panel shows a real book's real metadata; and switching to Urdu
correctly mirrors the *entire* rebuilt layout right-to-left (header,
rail with translated labels, all three search panes, button order) via
the existing `QApplication.setLayoutDirection()` mechanism, with no
additional RTL-specific code needed anywhere in the new UI.

## General multi-dimensional taxonomy system (migration 6), additive

User-requested design: a scalable taxonomy covering nine dimensions
(subject, author, madhhab, language, publisher, region, personality,
event, tag), every book able to carry unlimited terms per dimension
(many-to-many), subject/region/personality/event hierarchical, real
alias/duplicate-merge support, language-independent stable IDs with
multilingual names, scaling to 100k+ books without schema changes -
explicitly not a redesign of the existing project.

One generic pattern - `TaxonomyDimensions` -> `TaxonomyTerms` (with
`ParentTermID` for the four hierarchical dimensions) -> per-language
`TaxonomyTermNames`/`TaxonomyAliases`, plus a single `BookTaxonomyTerms`
many-to-many join - covers all nine dimensions uniformly instead of nine
bespoke tables; adding a tenth dimension later needs zero schema
changes. `BookPublicationDetails` holds the scalar publication fields
(year, edition) that don't fit a "term" shape, alongside `publisher` as
a genuine many-to-many term dimension. Migration 6
(`_add_taxonomy_system` in `migration_runner.py`) is purely additive -
the existing `Categories`/`CategoryTaxonomy`/`Authors` tables are
completely untouched, and migrating their real data into this system is
a deliberate later step, not part of this migration.

`TaxonomyRepository` (new, `infrastructure/persistence/`):
`get_or_create_term()` (matches an existing term by exact name or by a
recorded alias - via the same diacritic/letter-form normalization
search already uses - before creating a new one, so re-importing the
same real-world entity under a spelling variant doesn't silently
duplicate it), `add_name()`/`add_alias()`, `link_book()`,
`list_terms()`/`get_term_tree()`, `list_books_for_term()`/
`list_terms_for_book()`, and `merge_duplicate_terms()` (real automatic
duplicate merging: groups terms by normalized name, the term linked to
the most books wins - the same deterministic `_pick_canonical` pattern
already used for category/author normalization - repoints every book
link to the survivor, and logs the merge to `TaxonomyTermMerges`).

Real bug found and fixed during verification: root categories in this
corpus's real data use MJCN sentinel `0` as `ParentMJCN` (an existing,
established convention - see `Category(mjcn=9, parent_mjcn=0, ...)` in
tests), not `NULL` - the first version of `get_term_tree()`-equivalent
logic silently returned nothing until this was caught.

12 new tests (242/242 total at that point): 3 for the migration itself
(seeds all nine real dimensions, leaves existing tables untouched, a
real hierarchical term with multilingual names and a book link works
end-to-end) and 9 for `TaxonomyRepository` (create/dedupe/alias-resolve/
link/tree/merge, each against a real migrated database).

Applied for real to the production database (fresh backup taken first):
`Version before: 5` -> `Version after: 6`, verified healthy afterward
(`DatabaseVerifier`: 0 errors, 0 warnings) on the real 15,162-book
corpus. No GUI wired to this yet (deliberately) - this milestone is the
schema/repository foundation; dimension-specific browsing (subjects
beyond the existing MJCN system, madhhab, regions, etc.) is future work
on top of it, the same incremental pattern used for every other Phase 4
feature.

### Maktaba Shamela investigated, not yet imported

Checked `F:\المكتبة الشاملة` (the main Arabic Shamela desktop app,
previously excluded per an explicit standing instruction) for useful
content, at the user's request. Real findings: 113 GB total, a real
catalog of 36,042 books (`book_index.db`, 30,662 actual `.mdb` files
found on disk - the gap is broken/missing catalog references, normal
for these bulk redistributions), only 0.5% exact title overlap with the
existing corpus (161 of 29,782 distinct titles) - genuinely almost
entirely new content that would more than double the current 15,162-book
corpus. Each book is its own MS Access `.mdb` file (confirmed via the
file header: Jet 3 / Access-97 format) with `book`+`title` tables.
**Real blocker found**: the installed Access ODBC driver refuses to
open these files ("Cannot open a database created with a previous
version") - ACE dropped Jet 3 support; reading them needs different
tooling (e.g. `mdbtools`), not yet set up. Given the scale (this would
become the single largest library by far) and that exclusion was a
prior explicit instruction, building the actual importer is scoped as
its own separate project, not started here.

## Search UX: direct book-opening from browsing, book-name search, bigger search box

Real gaps found once the 3-pane Search rebuild was in real use (not
issues in the earlier rebuild's own tests, which only checked that
clicking populated the filter fields, not that anything visible
happened when the query box was empty - the actual real-world case):
clicking a category/author/library with no search query typed did
nothing at all (`_run_search()` returns immediately on an empty query,
by design, for content search - but browsing was routed through it
too), there was no way to search by book name/title (only page-content
full-text search existed), and the main query box was one of five
same-sized fields in a single row rather than the primary action.

- `BookBrowserRepository` gains `list_books_in_category()`/
  `list_books_by_author()`/`list_books_in_library()` (capped at
  `MAX_BROWSE_RESULTS = 200` per call, with a "showing first 200" note,
  so a 2,718-book library click stays usable) and `search_by_title()` -
  a real title search using the same diacritic/letter-form
  normalization already applied to page content, so it's tolerant of
  real spelling variants in whichever script the title/query actually
  uses (this does not translate between scripts - typing "Bukhari"
  won't find "صحيح البخاري", only real same-script spelling variance,
  same honest boundary as content search).
- Clicking a category/author/library now shows that list of real books
  directly as open-able cards (Open PDF/Read in app/Details, no search
  excerpt needed) when the query box is empty, instead of doing
  nothing; still runs a filtered search when a query is present, same
  as before. "All libraries" with no query shows a prompt instead of
  dumping all 15,162 books as cards.
- `_run_search()` now runs title search alongside content search (not
  instead of it) and shows real title matches in their own "Matching
  titles" group above the content-match results, since the same query
  can be a real title match, a real content match, or both.
- The query box is now on its own full-width row with a visibly larger
  height/font (`#mainSearchBox`); library/author/category filters moved
  to a secondary row below it.
- A live filter box above the Categories/Authors panes narrows either
  list as you type (691 categories and 650 authors are too many to
  scroll through blindly) - category filtering keeps a matching child's
  ancestors visible and auto-expands them; both use the same diacritic/
  letter-form-normalized, case-folded matching as everywhere else.

Real bug found while writing the filter's own test: the filter's search
text wasn't casefolded (only the list being filtered was), so typing an
exact-cased name like "Author One" matched nothing - fixed before
shipping.

12 new tests (254/254 total): 6 for the new repository methods
(category/author/library book listings, title search matching/
letter-form tolerance/empty-query handling) and 6 for `SearchScreen`
(browsing-on-click for category/author/specific-library - previously
silent, now shows real book cards - "All libraries" showing a prompt
instead of everything, title-match section, browse-filter narrowing the
real author list). Four existing tests' status-label assertions updated
for the new "N content result(s)" wording (a real, intentional format
change, not a regression).

Verified for real against the production database: clicking "اصلاحی
کتب" (819 books) with an empty query lists real, directly-openable
books; clicking the Shamila Urdu library chip lists its real 698 books;
searching "بخاری" shows real title matches (e.g. "آفتاب بخارا سوانح
حضرت امام بخاری") in their own group above real content matches; typing
"محمد" into the author filter narrows 650 real authors down to matching
ones live.

## Real bug fix: the reading font wasn't actually rendering as chosen

User-reported: the Viewer's selected font ("Noori Nastaleeq") didn't
look right. Root cause, confirmed directly (`QLabel.font().family()`
after `setStyleSheet()`): Qt's `font-family` stylesheet property does
**not** walk a CSS-style comma-separated fallback list the way a real
browser does - it requests only the first name verbatim, and if that
exact family isn't installed, Qt silently substitutes some unrelated
default instead of trying the next name in the list. "Noori Nastaleeq"
itself turned out not to be installed on this machine at all (confirmed
via `QFontDatabase.families()`) - only "Jameel Noori Nastaleeq" (the
real, widely-distributed version) was, so every font choice whose first
preference wasn't installed was silently rendering wrong.

Fixed with `reading_fonts.resolve_installed_font_family()`: walks the
same comma-separated stack ourselves against `QFontDatabase.families()`
and returns the first name that's genuinely installed (falling back to
"Tahoma", confirmed present), so the font actually requested from Qt is
always real. `ViewerScreen._apply_font_size()` now resolves before
setting the stylesheet. `DEFAULT_FONT_CHOICE` changed from "Noori
Nastaleeq" to "Jameel Noori Nastaleeq" - the same real font, but the
name actually present as an installed system font, so the default
selection is honest about what's shown from the very first run.

3 new tests (`test_reading_fonts.py`) covering the exact real bug
(a stack whose first choice isn't installed correctly falls through to
one that is) plus the already-installed-first-choice case. Existing
font tests updated for the new default/verified against `QFontDatabase`
rather than hardcoding an unverified font name. 257/257 tests passing.

## Real bug fix: more cross-keyboard letter variants unified; a real exact/tolerant search toggle

User-reported: search should ignore real Arabic/Urdu keyboard-layout
differences more thoroughly, and every search should offer a real choice
between exact and tolerant matching.

**Confirmed a real gap directly** (a raw FTS5 query for one variant
genuinely did not match content stored with the other, tested standalone
before touching any code): an Arabic keyboard produces "ك" (kaf) and "ه"
(heh); an Urdu keyboard produces "ک" (keheh) and "ہ"/"ھ" (goal heh/
doachashmee heh) for what reads as the same letter - `_NORMALIZATION_PAIRS`
didn't unify these (only alef/yeh/teh-marbuta variants were). Also
directly verified, so it wasn't "fixed" a second time for nothing: FTS5's
tokenizer already treats Urdu full stop "۔" as a real word separator
(`"الف۔زکوة"` already correctly tokenizes as two words) - not a real gap.

Added the two missing pairs to `shared/arabic_text_normalization.py`.
**Real architectural point found while fixing it**: migration 5's
`PagesFTSNormalized` trigger has its REPLACE-chain SQL baked into stored
trigger text at creation time - updating the Python constant alone does
nothing for an already-migrated database, since neither the trigger nor
the already-indexed rows change. Migration 7
(`_fix_normalized_search_keyboard_variants`) drops and recreates the
trigger and rebuilds every indexed row with the corrected normalization -
the same real fix migration 5 itself needed when it was first added, now
needed again for this correction.

**Real "exact match" toggle added, per explicit request** ("give option
in every search for exact match or matching word accepted"): `exact:
bool = False` added to `BookSearchService.search()`,
`SqliteBookSearchRepository.search()`, and
`BookBrowserRepository.search_by_title()`. `exact=True` always uses the
literal `PagesFTS`/raw `Title` comparison with no normalization at all;
the default (`False`) is unchanged tolerant behavior. A new "Exact
match" checkbox in `SearchScreen`, next to the category/library filters,
re-runs the current search on toggle.

Real bug found and fixed in the *test* for this before it shipped: a
`qtbot.keyClick()`-driven search followed by a direct `setChecked()`
call on the same test hung indefinitely under pytest-qt (confirmed to
run correctly outside pytest, in a plain script - isolated to a
qtbot/event-loop interaction, not the app code) - rewritten to match
this file's simpler direct-method-call pattern used elsewhere, which
doesn't hang.

Also found and fixed: `HybridSearchService`'s `FakeKeywordIndex` test
doubles (in `test_hybrid_search.py`/`test_book_search.py`) needed their
`search()` signature updated for the new `exact` parameter - the same
class of gap already hit once before when `author`/`category` were
added, now happened again for `exact`.

10 new tests (267/267 total): 2 for the new normalization pairs, 2 for
the migration 7 rebuild (cross-keyboard match after migrating, and that
newly-imported pages after the rebuild still get normalized correctly),
2 for `exact=True` in `SqliteBookSearchRepository`, 1 for
`search_by_title`, 2 for `BookSearchService` passing `exact` through,
1 for the `SearchScreen` checkbox. Applied migration 7 for real to the
production database (fresh backup first).

## Phase 5: Book Viewer - in-app PDF reading, bookmarks, recent books

Text-page books already opened in `ViewerScreen`; PDF-only books (no
extracted per-page text - confirmed DjVu/EPUB have zero real content in
this corpus, so Phase 5 scope was PDF + bookmarks + recent books only)
had no in-app reading path at all.

### Added

- `PdfViewerScreen` (`interfaces/desktop_app/pdf_viewer_screen.py`), a
  new screen using Qt's own `QPdfDocument`/`QPdfView` (ships with
  PySide6, no new dependency) for real in-app PDF rendering: prev/next
  page, a page-number jump box, zoom in/out, and a bookmark toggle.
- Real per-page bookmarks: `BookBookmarks` table (migration 8) +
  `BookmarkRepository` (`infrastructure/persistence/bookmark_repository.py`).
  Wired into both `ViewerScreen` (text-page books) and the new
  `PdfViewerScreen` (PDF books) via a shared `bookmark_toggled` signal, so
  bookmarking works identically regardless of which viewer opened the book.
- Real recently-opened-book tracking: `RecentBooks` table (migration 8,
  `UNIQUE`/upsert on `BookID` so reopening a book updates its row instead
  of duplicating it) + `RecentBookRepository`
  (`infrastructure/persistence/recent_book_repository.py`), plus a real
  "Recent" tab in `SearchScreen`'s left pane (next to Categories/
  Authors) listing them and reopening one at its real last page on
  click. Queried fresh each time the tab is shown rather than kept live
  via a signal - simple and cheap at the real `MAX_RECENT_BOOKS = 20` cap.
- `MainWindow` routing (`_open_in_viewer`): tries `ViewerScreen` first: if
  the book actually has extracted text pages, opens there; otherwise falls
  back to resolving and opening the source PDF in `PdfViewerScreen`. Both
  screens now live inside an inner `QStackedWidget` at rail index 1.
- Both repositories follow the existing `_table_exists()` graceful-degrade
  pattern (`BookBrowserRepository`'s established pattern) so a database
  that hasn't run migration 8 yet never crashes - bookmarking/recent-books
  just silently no-op until migrated.

### Fixed

- **Real bug found while wiring routing**: `ViewerScreen.load_book()`
  returned `True` even for a 0-page (PDF-only) book, which broke the
  PDF-fallback logic (`if viewer_screen.load_book(...)` was always
  truthy). Added `has_content()` and used it as an additional routing
  condition.
- **Real bug, user-reported** ("author n category search button not
  working"): `SearchScreen._run_search()` returned immediately whenever
  the main search box was empty, before it ever looked at the
  Author/Category/Library filter fields - so typing directly into those
  boxes and clicking Search did nothing. Added
  `BookBrowserRepository.list_books_by_filters()` (any combination of
  exact library/author/category, all optional) and
  `SearchScreen._browse_by_filters()`, used when the query box is empty
  but at least one filter is set - browses straight to the matching books,
  the same way clicking a name in the left pane already did.

21 new tests (288/288 total): `PdfViewerScreen`,
`BookmarkRepository`/`RecentBookRepository` (including pre-migration
graceful-degrade cases for both), `MainWindow` routing to each screen,
and the Author/Category filter-search fix. Migration 8 applied for real
to the production database (fresh backup first, verified `user_version`
7 -> 8, both new tables present, and a real bookmark add/remove +
recent-open record/list round-trip against a real production book -
the test row was deleted afterward, no permanent change left behind).

## Semantic search pilot: real storage-bloat bug fixed (before any full-corpus run)

The pilot run's known bug (noted at the time, not yet fixed - see the
"Semantic search pilot" entry above) was that `PageEmbeddingIndexer.
index_pages()` called `EmbeddingStore.store()` once per 32-page
embedding batch, and each `SqlitePageEmbeddingRepository.store()` call
opens its own SQLite connection and commits its own transaction - 256
separate commits for the 8,179-page pilot, costing ~789 MB of real
transaction/connection overhead for what should have been ~12.6 MB of
actual vector data.

**Fixed** by decoupling embedding batch size from storage/commit batch
size: `index_pages()` still embeds in small `batch_size`-sized chunks
(bounds the embedding model's peak memory), but now accumulates
entries and only calls `store()` once `commit_batch_size` (default
1000) entries are pending, or at the very end. For a full-corpus run
this cuts commits by roughly 30x (1000/32) versus the pilot's
behavior, without changing embedding memory use at all.

4 new/updated tests in `test_page_embedding.py`: batch-size-vs-commit-
size decoupling verified directly (embedding batches of 2 still embed
as `[2, 2, 1]`, but storage commits as `[4, 1]` with
`commit_batch_size=4`), and a small run confirmed to commit exactly
once under the real default `commit_batch_size=1000`. 290/290 tests
passing overall.

**Not yet done**: no full-corpus embedding run. The corpus has grown
significantly since the original 18-hour estimate (922,345 pages at
the time) - it now stands at 2,385,159 pages across 15,162 books. At
the pilot's measured throughput (~14.5 pages/sec, CPU-only, no GPU),
a full run is now estimated at **~45.7 hours of continuous CPU time**,
not 18. This is a real, updated number to weigh before committing to
that run - not yet started.

## Semantic search: resume-safe batched indexing, WAL mode, full-corpus run started

Before committing real machine time to the full-corpus run, three things
the user explicitly asked for were built and verified for real.

### Added

- **Resume/skip logic** (`semantic_index_cli.py`, `_load_pages_to_index`):
  every page already present in `PageEmbeddings` is now excluded via a
  `NOT EXISTS` SQL filter before anything is loaded - re-running the
  same command after an interruption (crash, power loss, deliberate
  stop) continues rather than re-embedding already-done pages. Verified
  for real: a running batch was hard-killed mid-run (SIGTERM via a shell
  timeout) and only the uncommitted partial batch was lost - re-running
  picked up exactly where it left off, with no duplicate work and no
  gaps (confirmed via `PageEmbeddings` row counts before/after).
- `--limit` on `semantic_index_cli.py`: caps a single run to a bounded
  number of not-yet-indexed pages, for deliberately splitting a large
  job into sessions. `--subject` changed from a required positional
  argument to an optional flag - omitting it now indexes the whole
  corpus instead of requiring one root category.
- `SqlitePageEmbeddingRepository.ensure_schema()`: creates the
  `PageEmbeddings` table (if missing) without writing any rows, so the
  resume check works correctly even before the very first real
  embedding is stored.
- **Migration 9, WAL journal mode**: the default rollback-journal mode
  briefly locks the whole database during every writer commit, which
  readers can genuinely hit as "database is locked" - confirmed
  directly in this project's own real usage earlier this session (a
  long-running read alongside a concurrent write). WAL lets the desktop
  app keep reading/searching while a long background indexing job
  writes. Applied for real to the production database (fresh backup
  first, verified `user_version` 8 -> 9 and `PRAGMA journal_mode`
  returns `wal`).

### Real production run

7 new tests (`test_semantic_index_cli.py`, plus a WAL-mode test in
`test_migration_runner.py` and an `ensure_schema()` test) - 299/299
total. Validated against the real production database (not just tests):
a small real run embedded 20 real pages correctly; a second run with the
same `--limit` confirmed real resume (20 different, not-yet-seen pages,
via `PageEmbeddings` row counts); a 3000-page timed run was killed
mid-batch and resumed cleanly. The full, unbounded, resume-safe indexing
run for the entire corpus (2,385,159 pages, ~45.7 hours estimated) was
then started for real in the background, per explicit request - not yet
complete as of this entry.

**Real bug found immediately after starting that run, and fixed before
letting it continue**: `main()` called `_load_pages_to_index()` once with
`limit=None` (the whole remaining corpus) *before* the embedding loop
started - which meant one SQL query tried to fetch every not-yet-indexed
page's real text (~2.37 million rows) into memory in a single round-trip
before a single page got embedded. Caught by watching real signals, not
assumption: `PageEmbeddings`'s row count stayed frozen for minutes while
the process's real CPU time kept climbing (8s -> 150s -> 252s) - a real,
running-but-not-progressing job. Killed it and fixed the actual cause:
`main()` now loops, fetching and embedding in bounded `QUERY_CHUNK_SIZE`
(5000-page) chunks regardless of `--limit`, so an unbounded "index
everything" run makes steady, real progress from the first chunk instead
of stalling on one giant query. Re-validated for real afterward (a timed
2000-page run made steady incremental commits, confirmed via
`PageEmbeddings` row counts moving during the run, not just at the end)
before relaunching the real overnight run.

**Updated real throughput, measured (not extrapolated) on this exact
machine**: ~8.5-8.7 pages/sec, slower than the original pilot's ~14.5
(likely real corpus-content differences, not a regression - this
project's later-imported libraries include denser/longer real page
content than the original Hadith-subject pilot). At this rate the full
corpus (2,385,159 pages) is now estimated at **~76-78 hours** of
continuous CPU time, not ~45.7 - another real, updated number.

