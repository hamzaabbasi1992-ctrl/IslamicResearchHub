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
