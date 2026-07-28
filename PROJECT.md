# Islamic Research Hub AI — Project Plan

Last updated: 2026-07-29 (kept in sync with `CHANGELOG.md`, which is the
authoritative detailed history — this file is the current-status summary).

## Goal

An offline-first Islamic research platform: one master SQLite database
(`data/books.db`) shared across a fast, high-quality search engine,
Windows desktop app (first), and Android app (later). Multiple source
libraries (Maktaba Jibreel, Maktaba Al-Maknoon, PDF collections) are
imported into one corpus, deduplicated, and searchable together while
staying individually traceable via `LibraryID`.

## Architecture

Layered, modular, under `src/islamic_research_hub`:

- `domain`: stable domain models (`Book`, `Category`, `Chapter`, `Page`,
  `Migration`, `VerificationReport`, etc.), framework-free.
- `application`: use cases and orchestration (`BookSearchService`,
  `HybridSearchService`, `LibraryAnalyzer`, `MasterDatabaseBuilder`, ...)
  behind `Protocol` ports.
- `infrastructure`: concrete adapters — SQLite persistence
  (`MasterBookRepository`, `MigrationRunner`, `DatabaseBackupService`,
  `DatabaseVerifier`, `SqliteBookSearchRepository`, ...), reporting.
- `interfaces`: CLI entry points (one per capability - `search_cli`,
  `migrate_database_cli`, `verify_database_cli`, `database_backup_cli`,
  `*_import_cli`, ...) and the local web app (`web_app.py`).
- `shared`: cross-cutting utilities (`arabic_text_normalization`,
  `title_cleanup`, `logging_config`).
- `config`, `domain/repositories`: currently empty placeholders, kept
  from the original scaffolding. Not populated - everything that would
  live there (repository contracts, hardcoded paths) has worked fine as
  `Protocol`s in `application/` and CLI defaults so far. Revisit only if
  a real need appears; don't populate them speculatively.

Dependencies point inward (domain has no outward imports; infrastructure
implements application's `Protocol`s; interfaces wire concrete adapters
to services). SQLite is the persistence choice; `data/` and `data/backups/`
are gitignored.

## Phased roadmap (governs what gets worked on)

Strict phase discipline: each phase must be complete before the next
starts. No side improvements, no premature optimization, no unrequested
AI work outside Phase 6. See `CHANGELOG.md` for the detailed history and
real-data validation behind every item below.

### Phase 1 — Import System: **complete**

- Maktaba Jibreel (Mobile), `.mjbz` — mature, production.
- Maktaba Jibreel (Desktop), `.mjbx` (encrypted, decryption formalized) — complete.
- Maktaba Al-Maknoon, pre-extracted PDF text — hardened against corrupted files.
- Generic PDF (native-text-layer only) — evaluated (1.7-5% real yield across
  the corpus, almost entirely scanned images), deliberately not built;
  PDF collections stay metadata-only (title/path, no text).
- Shamela — importer not yet built (see Phase 7); the earlier "excluded,
  explicit standing instruction" was reversed at the user's request.
- Calibre — not started, optional/low priority.

### Phase 2 — Master Database: **complete**

- Database verification tool, backup/restore tooling, versioned migration
  system (`PRAGMA user_version`, 7 real migrations applied to production
  - migrations 6/7 added a general multi-dimensional taxonomy schema and
  a cross-keyboard search-normalization fix, both after Phase 4).
- Authors normalized (650 authors, 4,466 books).
- Categories normalized into a cross-library taxonomy (691 categories,
  shared MJCN scheme across the two Jibreel libraries).
- Volumes modeled as a Series entity (412 series, 2,452 books).
- Footnotes — a real `Footnotes` table (BookID, PageNo, FootnoteText) now
  exists and is populated: originally closed as "no source data exists"
  (true for every library at the time), reopened after Maktaba Shamila
  Urdu was added, whose per-book format has real footnote content -
  67,056 real footnote rows imported and verified.
- Library IDs — in place since the multi-library work.

### Phase 3 — Search: **complete**

- FTS5 keyword search, bm25 ranking, `snippet()` highlighting.
- Arabic/Urdu-normalized search index (diacritics stripped, letter-form
  variants unified) - 2,046,888 pages indexed, verified with real
  variant-spelling queries.
- Filters: library, author, category.
- Boolean search (AND/OR/NOT, phrases, prefix) - verified via FTS5's
  native syntax; a real web-app crash on malformed queries was found and
  fixed along the way.
- Root search - evaluated (no reliable offline Arabic morphology option),
  deliberately not built per explicit decision.
- Page navigation - confirmed working (PDF `#page=N`, in-app `?page=N`).
- Search-normalization enhanced after Phase 4 (migration 7, real bug
  found and fixed): real Arabic/Urdu cross-keyboard letter variants now
  unified too (kaf ك/ک, heh ه/ہ/ھ), not just diacritics/alef/yeh. A real
  exact-vs-tolerant match toggle was added to every search entry point
  (`exact=` parameter + a Search-screen checkbox) per explicit request.
  Book-name/title search (script-tolerant, not just page-content search)
  added alongside content search in the same Phase 4 rebuild.

### Phase 4 — Desktop GUI (PySide6): **done**

- Search screen - **done**: `interfaces/desktop_app/` (`MainWindow` nav
  rail + `SearchScreen`), wired to the real, already-tested
  `BookSearchService`/`BookBrowserRepository` - no new search logic.
  Verified for real: searched the production database from the actual
  packaged `.exe`, screenshotted, 30 correct results with visible
  highlighting. Later rebuilt as a real 3-pane layout (category/author
  browsing tree on the left, an inline detail panel on the right) to
  match the Phase 4 design preview's actual structure, not just its
  colors - see the CHANGELOG entry "Phase 4 structural rebuild".
- Header bar - **done**: wordmark, five live corpus stats (books/
  libraries/authors/categories/series), and a language switcher that
  shares the same `Translator` as Settings. Icon+label nav rail
  (`QToolButton`, icons rendered from the design preview's own SVG
  paths).
- Packaging - **done**: `build_installer.ps1` produces a standalone,
  portable `installation/IslamicResearchHub/` folder (PyInstaller
  `--onedir`) that runs without a separate Python install. README in
  English/Urdu/Arabic included. Not an installer/uninstaller yet - a
  portable folder.
- Viewer - **done** (page reading, no TOC yet): `ViewerScreen`, wired to
  the real `BookBrowserRepository.get_book_detail()`. Reachable from a
  search result's "Read in app" button, which jumps straight to the
  matched page. Verified for real: searched the production database,
  opened a real 324-page book at the exact matched page, screenshotted.
- Import Manager + Duplicate Review - **done**, combined into one
  `ImportScreen`: real library-sources table, and duplicate-candidate
  review wired to the already-tested `DuplicateCandidateRepository`
  (scan, and the safe empty-stub cleanup that never touches a pair with
  real content on both sides). Verified for real: all 9 libraries with
  correct counts (15,127 total), a fresh scan against the real database.
  Later gained a real "Add new library" form (folder picker, format
  dropdown, `LibraryImportWorker(QThread)` running the same scanner/
  builder classes the CLI importers use, off the GUI thread) - see the
  CHANGELOG entry "Phase 4 structural rebuild". Jibreel Desktop
  (`.mjbx`, encrypted) stays CLI-only - it needs extra configuration
  (SQLite DLL path, password) this simple form doesn't have fields for.
- Settings - **done**: real language switching (English/Urdu/Arabic) via
  a new `Translator`, with genuine whole-app RTL/LTR mirroring
  (`QApplication.setLayoutDirection`) - fulfills what the design preview
  promised, confirmed to still mirror correctly (header, rail, all three
  search panes) after the later structural rebuild. Also: a persisted
  default reading font size *and font family* (10 real Urdu/Arabic
  fonts, `reading_fonts.py`), and a real About section. Found and fixed
  a real bug in the process: `MainWindow` was using the *real*
  Windows-registry-backed `QSettings` in every test, and had already
  leaked a stray `language=ur` value into the real registry before that
  was caught - fixed with dependency injection, same pattern as
  everywhere else `QSettings`/`Translator` are used.
- Logs, Book Details - **done**: `LogsScreen` reads the real application
  log (newest 500 lines). Details was originally a popup dialog
  (`BookDetailsDialog`); later replaced with the inline detail panel in
  Search's 3-pane rebuild (the dialog file was removed as dead code).
  Both wired to real data, verified for real against the actual
  production log and real search results. Closes out the original
  8-tab Phase 4 list.

### Phase 5 — Book Viewer: **done**

PDF rendering, jump-to-page, bookmarks, recent books - the PySide6
desktop equivalent of the browser-based viewer already in the frozen web
app. DjVu/EPUB were evaluated and dropped from scope: confirmed zero real
content of either format exists anywhere in the corpus.

- `PdfViewerScreen` - **done**: real in-app PDF rendering via Qt's own
  `QPdfDocument`/`QPdfView` (ships with PySide6, no new dependency) -
  page navigation, a page-number jump box, zoom, bookmark toggle.
- Routing - **done**: `MainWindow` opens text-page books in the existing
  `ViewerScreen` and falls back to `PdfViewerScreen` for PDF-only books,
  both inside one stacked widget at the Viewer rail position.
- Bookmarks - **done**: real per-book, per-page bookmarks
  (`BookBookmarks` table, migration 8, `BookmarkRepository`), wired into
  both viewer screens via a shared toggle signal.
- Recent books - **done**: `RecentBooks` table (migration 8,
  upsert-on-reopen) + `RecentBookRepository`, plus a real "Recent" tab
  in the Search screen's left pane (alongside Categories/Authors),
  listing real recently-opened books and reopening one at its real last
  page on click.
- Real bug fixed along the way: the Search screen's Author/Category
  filter fields did nothing when clicked with an empty search box (the
  empty-query check short-circuited before the filters were read) - see
  CHANGELOG.
- 21 new tests (288/288 total). Migration 8 applied for real to the
  production database (fresh backup first, verified `user_version` 7 ->
  8, both new tables present, and a real bookmark + recent-open
  round-trip against a real production book).

### Phase 6 — AI: **not started under phase discipline**

Semantic search, embeddings-based QA, citation engine, cross-book
comparison, research assistant. Note: a semantic search pilot
(sentence-transformers, hybrid RRF fusion with keyword search) already
exists, built before the phased roadmap was adopted and kept as-is per
explicit decision - it is not formally "Phase 6 work" and hasn't been
scaled to the full corpus.

- **Storage-bloat bug: fixed.** The pilot's per-32-page-batch commit
  pattern (256 commits, ~789 MB overhead for ~12.6 MB of real vector
  data) is fixed - see CHANGELOG. Storage now commits in much larger,
  far less frequent batches (default 1000 entries), independent of the
  embedding batch size.
- **Resume-safe batched indexing: done.** `semantic_index_cli.py` skips
  every page already embedded (`NOT EXISTS` against `PageEmbeddings`)
  and supports `--limit` for bounded, resumable batches - verified for
  real by hard-killing a run mid-batch and confirming a re-run resumed
  cleanly with no duplicate work and no gaps.
- **WAL journal mode: done** (migration 9, applied to production) - lets
  the desktop app keep reading/searching while a long background
  indexing job writes, instead of risking "database is locked".
- **Full-corpus run: started.** The original ~18 hour estimate was based
  on a 922,345-page corpus; the corpus has since grown to 2,385,159
  pages (15,162 books), so the updated estimate is **~45.7 hours** of
  continuous CPU time (no GPU on this machine). Started for real,
  unbounded, in the background, per explicit request - in progress, not
  yet complete.

### Phase 7 — Maktaba Shamela import + taxonomy GUI: **scheduled after Phase 6, not started**

Explicitly scheduled by the user to come after Phase 6, not before -
both items below are real, scoped, but deliberately deferred:

- **Maktaba Shamela importer**: `F:\المكتبة الشاملة`, 113 GB, 30,662
  real books, 99.5% new vs. the existing corpus (would more than double
  it). Investigated, not yet built - see CHANGELOG. Real blocker: the
  books are Jet 3/Access-97 `.mdb` files the installed ACE ODBC driver
  refuses to open; needs different tooling (e.g. `mdbtools`) before an
  importer can be written.
- **Taxonomy dimension browsing/tagging GUI**: migration 6 added the
  general nine-dimension schema (subject, author, madhhab, language,
  publisher, region, personality, event, tag) and `TaxonomyRepository` -
  see CHANGELOG. No data has been migrated into it and no GUI browses it
  yet; both are this phase's real work, not migration 6's.

## Items existing outside phase discipline (frozen, by explicit decision)

- **Local web app** (`web_app.py`, Flask): search, PDF page-jump, in-app
  reading. Built before the roadmap was adopted; kept working as-is; no
  further feature work until Phase 4 territory is reached, except direct
  bug fixes (e.g. the malformed-query crash fixed during Phase 3).
- **Semantic search pilot**: sentence-transformers + hybrid keyword/
  semantic fusion, built and validated on one subject (27 books) before
  the roadmap existed. Not scaled further until Phase 6.

## Additional libraries added outside the Phase 1 sequence

Phase 1 (above) covers the roadmap's original library list. Two more real
sources were found and imported afterward, at the user's request, each
checked for overlap before anything was imported:

- **Maktaba Islam** (`F:\MaktabaIslam`, ~3 GB): 94% title overlap with
  the existing corpus (same underlying platform as Maktaba Jibreel - same
  `.mjbz` schema, zero new code needed). Imported only the non-
  overlapping content: 48 books (12 of the 60 candidates were genuinely
  corrupted source files, correctly skipped) + 81 PDFs (metadata-only).
- **Maktaba Shamila Urdu** (shamilaurdu.com, downloaded and inspected):
  a genuinely different platform - only 3/695 titles (0.4%) overlapped,
  different scholarly tradition (Ahle Hadith/Salafi vs. the existing
  corpus's mostly-Deobandi lean). 698 books imported in total: 663 from
  `Books/` (own per-book SQLite schema, HTML-styled content stripped to
  plain text) plus, in a second pass after an initial report undercounted
  this collection (see the CHANGELOG correction entry), 15 real Hadith
  collections from `Hadith/` (Sahih al-Bukhari, Sahih Muslim, Sunan Abi
  Dawud, and 12 more) and 20 Quran-folder resources from `Quran/` (the
  base Arabic text, 7 translations, 12 tafsirs) - each its own schema,
  each with a dedicated reader. Its `fnotes` column (Books/) and
  `HadithHashiaText` commentary (Hadith/) are the first real footnote
  data found in this corpus - see the `Footnotes` table note under
  Phase 2 above.

## Not yet scheduled / future candidates

- **OCR**: now the single highest-value future item — most of the corpus
  (PDF Archive + Maknoon PDF collection + Jumma Bayanat, ~9,000 files) is
  metadata-only with no extracted text. Needs its own honest feasibility
  check (distinct from the native-text-extraction check already done for
  Phase 1) before any commitment.
- Duplicate candidate review (27 remaining Mobile/Desktop pairs).
- Performance index audit at the current, much larger corpus size.

(Maktaba Shamela and the taxonomy GUI - previously listed here - are
now formally Phase 7, above; scheduled after Phase 6 per the user's
explicit instruction.)
