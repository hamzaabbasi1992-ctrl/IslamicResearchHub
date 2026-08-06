# Islamic Research Hub AI — Project Plan

Last updated: 2026-08-05 (kept in sync with `CHANGELOG.md`, which is the
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

**AI provider policy (applies to every AI-heavy phase from Phase 9
onward)**: local, self-hosted open models are the default - preserves
offline-first (no internet requirement, no per-query cost, no data
leaving the machine, no third-party content moderation risk on
sensitive comparative-religion queries), and matches what's already
built (the embedding pilot uses a local `sentence-transformers` model
behind a `TextEmbedder` Protocol). Cloud APIs (OpenAI/Anthropic/Gemini,
or specialist cloud TTS/STT/translation services) are an **optional,
user-provided-key upgrade** for higher quality, wired in behind the
same `Protocol`-port pattern already used throughout `application/` -
swapping the underlying provider is meant to be cheap by design, not a
rewrite. Local stays the baseline everyone gets; cloud is opt-in, never
required.

The provider choice itself stays an implementation detail, not
user-facing jargon - most users don't know or care which underlying
model powers a feature. The UI names the *capability* ("AI Summary",
"Enhanced Voice", "Smart Search"), not the provider; an optional
Settings entry for "enable enhanced AI (requires internet + your own
API key)" is as technical as it should ever get for a general user.

## Internal dependency graph: what the data foundation unlocks

Real dependencies between the foundational data-layer pieces (built or in
progress now) and the later phases that need them - not a phase
renumbering, a map of *why* the foundation work matters before those
phases can start for real.

- **Paragraph IDs** (`Paragraphs.ParagraphID`, migration 13, `paragraphs_backfill_cli.py`)
  → the addressable unit every later citation-level feature points at.
  Needed by: Phase 10's citation graph (a link is only real if both ends
  resolve to an actual paragraph), Phase 10's contradiction/knowledge-gap
  detectors (need to cite *which* passage), Phase 11's AI research
  assistant (an answer must open the exact paragraph, not just a page),
  Phase 13's AI reading assistant, Phase 16's AI content generator (every
  generated claim needs a real source pointer).
- **Citation mapping** (`HadeesNumber`/`AyahNumber`, migration 14;
  `get_volume_siblings()` + `format_citation()`) → real, human-readable
  citation strings ("Book X, Volume Y, Page Z, Paragraph N" / a real
  hadith or ayah number) instead of internal row IDs. Needed by: every
  phase above that surfaces a citation to a user, not just internally.
- **Search indexes** (`BooksFTS`/`PagesFTS`/`FootnotesFTS`/`ParagraphsFTS`,
  all bm25-ranked, migration 15 completing the set) → the retrieval layer
  everything else queries against. Needed by: Phase 7 (already depends on
  it), Phase 10's cross-language/knowledge-gap work, Phase 11's AI
  assistant (retrieval-augmented generation needs a real retriever - this
  *is* that retriever), Phase 14's research workspace.
- **Taxonomy** (`TaxonomyDimensions`/`TaxonomyTerms`/`BookTaxonomyTerms`,
  migration 6 - schema exists, population is Phase 8) → the structured
  entity/subject graph. Needed by: Phase 10's knowledge graph and
  encyclopedia builder directly (an encyclopedia page *is* "everything
  linked to one taxonomy term"), Phase 15's educational features. Real
  gap today: `personality`/`event`/`madhhab`/`region`/`tag` dimensions
  are still empty placeholders (only `author`/`subject`/`publisher`/
  `language` are populated) - Phase 8 has to close this before Phase 10
  can build on it for real.
- **Metadata normalization** (`Books.AuthorID`, `Books.SeriesID`/
  `VolumeNumber`, `CategoryTaxonomy`, diagnostics coverage in
  `DatabaseVerifier`) → guarantees every record is reachable by a real
  identifier, not just free text, and that broken links get caught before
  they reach a user. Needed by: everything above, transitively - a
  knowledge graph or AI assistant built on inconsistent foreign keys
  fails silently in ways that are much harder to debug once AI-generated
  content is layered on top.

Deliberately **not** in this list: anything AI-generated (embeddings,
extraction, summarization). Every item above is real, verifiable,
non-AI infrastructure - the explicit point of building it first.

## Phased roadmap (governs what gets worked on)

Strict phase discipline: each phase must be complete before the next
starts. No side improvements, no premature optimization, no unrequested
AI work outside Phase 6. See `CHANGELOG.md` for the detailed history and
real-data validation behind every item below.

**V1.0 definition** (per explicit decision: think in terms of a 10-year
roadmap, not a v1.0 checklist - v1.0 should solve one problem extremely
well before anything else): **Phases 1-7** - find reliable information
across the whole unified library quickly, with accurate, real page
citations. Everything from Phase 8 onward is real, scoped future work,
not part of getting there. Modular by design already (`Protocol` ports
throughout `application/`, the optional `ai` extra in `pyproject.toml`)
- a user who never touches AI/voice/etc. still gets a fast, complete
library; those capabilities aren't required to get v1.0's core value.

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
  - **App-wide text retrofit: done** (see CHANGELOG). The above shipped
    real RTL/LTR *layout* mirroring, but per-screen *text* stayed
    hardcoded English outside Settings/HeaderBar - caught directly by
    the user ("whole maktaba doesnt convert to that language when i
    select it"). All 11 remaining screens (Home, Logs, AI Assistant
    panel, Taxonomy Browser, Citation/Event/Duplicate managers, Import,
    PDF Viewer, Viewer/Reader, Search) now take a required `Translator`
    and retranslate live on `language_changed`, not just on next
    launch. `i18n.py` grew from ~30 to 284 keys, real Urdu/Arabic text
    throughout (not placeholders). Already-rendered dynamic content
    (search results, an open book's own chapter titles) is real
    book/library data, not app chrome - left untranslated in place by
    design; a fresh action (new search, newly opened book) always
    renders in the current language.
- Logs, Book Details - **done**: `LogsScreen` reads the real application
  log (newest 500 lines). Details was originally a popup dialog
  (`BookDetailsDialog`); later replaced with the inline detail panel in
  Search's 3-pane rebuild (the dialog file was removed as dead code).
  Both wired to real data, verified for real against the actual
  production log and real search results. Closes out the original
  8-tab Phase 4 list.
- UI/UX redesign toward a modern research workspace - **done**, an
  11-milestone effort (approved via plan mode, backend/persistence
  untouched throughout - see each "Desktop app UI/UX redesign,
  Milestone N" CHANGELOG entry for full detail): a real design-token
  system (`Palette`/`Spacing`/`Type`) with live dark mode + font scale;
  Search and the Reader merged into one persistent `WorkspaceScreen`
  (`QSplitter`-based) instead of separate full-screen tabs, plus a
  collapsible AI-assistant panel (honest "similar books" chrome, no fake
  chat - no LLM exists anywhere in this codebase); a new Home dashboard
  (4 of 6 cards wired to real data; Collections and true AI Suggestions
  stay documented placeholders - no "list rated/bookmarked books" query
  or book-similarity method exists to back them); Duplicate Manager split
  into its own screen with a working session-only Skip and an honestly
  disabled Merge (no merge operation exists in the persistence layer);
  recent-search history + autocomplete; a friendlier default Logs view
  (raw log moved behind "Advanced"); 11 real keyboard shortcuts; and
  panel-collapse/expand animations. Full inline-style spacing/typography
  adoption of the new tokens was deliberately deferred - real, reviewable
  follow-up work once appearance can be confirmed visually (this sandbox
  cannot screenshot the running app). Test suite grew from 427 to 507
  across the whole effort, zero regressions at every step.
- **UI Polish Pass 2 - done** (see CHANGELOG). Reader widened, detail
  panel narrowed + made collapsible, result cards tightened, TOC/
  Bookmarks empty states added, toolbar grouped, stat separators added.
  Deferred on purpose: the Research/Reading Mode toggle (new
  functionality, not polish) and icon-only result buttons (lowest
  priority). Original queued notes kept below for reference.
- **UI Polish Pass 3 - done** (see CHANGELOG). Taxonomy Browser and
  Duplicate Manager empty/dead-space fixes, Home dashboard card height
  consistency.
- **Reader bug fixes - done** (see CHANGELOG). Three real bugs reported
  directly against the running app, all fixed: maximize/minimize doing
  nothing visible (siblings now fully hidden, not just shrunk to their
  minimum), the AI panel effectively invisible on wide/maximized windows
  (real stretch-factor fix, confirmed stable ~19.7% share at every window
  size tested), and stray "tofu" glyphs in reader text (invisible Unicode
  format characters now stripped at display time). Investigated but left
  as-is per direct instruction: none of the 10 Urdu/Arabic reading fonts
  offered in Settings are actually installed on the user's machine, so
  the font picker currently has no visible effect for Urdu/Arabic text.
- ~~UI Polish Pass 2 - queued, not started.~~ The deferred visual review
  above happened: the user had an outside architect-style review done
  against real screenshots of the running `WorkspaceScreen`, scored 8.5/10,
  confirmed no architecture/backend issues. Polish only, no new
  functionality, no schema/backend changes. Queued items, roughly
  priority-ordered:
  - Reader pane too narrow relative to search/metadata - widen it
    (~35%), at the expense of the metadata panel's width.
  - Make the metadata panel and TOC collapsible where they aren't
    already (TOC already collapses in the standalone reader via
    `_on_contents_toggled`/`animate_splitter_size` - needs checking
    whether that's true in `WorkspaceScreen` too, not assumed).
  - Reduce search result card height/padding; show more results per
    screen.
  - Real empty-state copy for the Assistant panel ("coming soon" reads
    unfinished), Bookmarks, and Contents panels - reuse the existing
    `EmptyStateLabel` pattern already used elsewhere, not a new pattern.
  - Separate Categories and Libraries visually in the sidebar.
  - Tighter visual hierarchy on book titles vs. metadata (size/weight).
  - Group/simplify the reader toolbar; convert repetitive text buttons
    to icon+text where it isn't already.
  - Stat-bar formatting (separators between book/library/author counts).
  - Verify the review's specific numbers (e.g. "reader is ~20% of
    screen") against the real current layout before implementing -
    reviewer's estimate from a screenshot, not measured.
  - **Not part of this pass, a separate later decision**: the reviewer
    also proposed a Research Mode / Reading Mode toggle (collapse
    search+sidebars for distraction-free reading). Genuinely a good idea,
    but it's new functionality, not polish - the review's own framing
    ("do not add new functionality") excludes it from this pass.

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
- **Research Notes: done** (added later, from a direct user feature
  request, not part of the original Phase 5 scope). Select text on any
  reader page, right-click, and save it into a real Microsoft Word
  (`.docx`) document under `Documents/Maktaba Research Notes/`, citation
  details attached automatically, existing content never overwritten.
  Kept in its own self-contained `research_notes/` package rather than
  spread across the usual layers, per the spec's own explicit ask. A
  `NotesStorage` Protocol (this project's existing TTS/voice-search
  adapter idiom) keeps the local `.docx` backend swappable for a future
  cloud one without touching the manager or dialog. See CHANGELOG for two
  real bugs found via manual verification (a settings-persistence bug and
  a Word-file-lock error path), both fixed and confirmed.

### Phase 6 — Real differentiators, buildable now: **done**

Added after an explicit push to prioritize what's actually unique to
this project over generic AI-wrapper features - the test applied: could
a generic tool (any PDF-AI wrapper, ChatGPT, NotebookLM) do this with
*any random* PDF collection? If yes, it's not a differentiator. These
items fail that test - they specifically require this project's
already-unified, cross-library, deduplicated corpus - and need no new
AI capability, only infrastructure that already exists:

- **Footnote-layer search: done.** `Footnotes` (67,056 real rows) is
  now genuinely indexed - `FootnotesFTS`/`FootnotesFTSNormalized`
  (migration 10), a real `scope` parameter (`"content"`/`"footnotes"`/
  `"both"`) through the full search stack, and a "Main text / Footnotes
  / Both" dropdown in the Search screen. Applied to production and
  verified with a real query. See CHANGELOG.
- **Cross-library edition/variant comparison: done.** No single-source
  tool (Shamela alone, Maknoon alone) can compare *its own* editions
  against each other. `BookComparisonRepository.compare()` computes a
  real page-by-page `difflib` similarity between two candidate books,
  honestly reporting `None` (not a misleading 0%) when pagination
  doesn't overlap. Wired into `ImportScreen`'s duplicate-review table
  as a real "Compare" button/dialog. See CHANGELOG. Verified against
  2,302 real stored candidates: found genuinely useful signal beyond
  title-matching alone - two same-titled pairs turned out to be very
  different content (as low as ~0.003% similarity), cases where
  title-matching alone would have wrongly suggested "probably the same
  book."
- **Real, full-corpus PDF-extractability scan: done** (not part of the
  original Phase 6 scope, but directly informs it - see CHANGELOG).
  Scanned all 5,914 PDF-only books across the three libraries with no
  companion index: **1,101 (18.6%) have a real extractable native text
  layer** - far above the old corpus-wide "1.7-5%" estimate (Jumma
  Bayanat alone is 32.3%) - and **2,139 (36.2%) have a real outline/
  bookmark structure**. Real, accurate scoping data for a future
  no-OCR-needed import of those 1,101 books and a TOC-only import of
  the outline books; the extractor/importer itself is not yet built.
- **Heading-only "stub book" PDF fallback: done** (not part of the
  original Phase 6 scope, but the same "use the corpus we already have"
  differentiator - see CHANGELOG). Investigated a real user report
  (screenshot of an almost-blank page) and found it's systemic in
  specific libraries (Maktaba Jibreel Desktop 86%, Al-Maknoon 66% of
  books), not a bug - confirmed by decrypting the original source
  directly. Built real, verified matching against the corpus's own PDF
  Archive libraries (direct source resolution + fuzzy title matching +
  Jibreel's own embedded PDF-filename cross-reference, the last of
  which required backfilling a field that had been read into memory at
  import time since day one but never persisted): **1,202 of 2,368
  stub books (50.8%) now offer a real fallback PDF** in the Viewer,
  opt-in via a clearly-labeled banner.
- **Real structural markup + bibliographic completeness for Shamila
  Urdu: done** (see CHANGELOG). Shamila Urdu's real (undocumented) span
  classes let heading structure and embedded Arabic-script quotations
  survive HTML-stripping instead of flattening to one plain-text blob -
  applied to all 698 already-imported books for real (283,425 pages,
  88,185 footnotes reformatted). Publish Year, previously discarded
  unread, is now captured (61.7% of books had one) and backfilled.

### Phase 7 — AI: semantic search: **done**

Semantic search, embeddings-based QA, citation engine, cross-book
comparison, research assistant. Note: a semantic search pilot
(sentence-transformers, hybrid RRF fusion with keyword search) already
exists, built before the phased roadmap was adopted and kept as-is per
explicit decision - it is not formally "Phase 7 work" and hasn't been
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
- **Full-corpus run: done.** Ran unbounded in the background over
  several sessions (resumable throughout via migration 9 + the
  resume/skip logic above; survived at least one real interruption for
  a competing write-lock from a concurrent backfill job, resumed
  cleanly). Real completion, verified directly: **every one of the
  1,697,553 pages with real (non-whitespace) content is embedded** -
  the other 687,606 of the corpus's 2,385,159 total page rows are
  either NULL or whitespace-only content with genuinely nothing to
  embed, not a gap. A real bug was found and fixed right after
  starting it (see CHANGELOG: an unbounded run tried to load the
  entire remaining corpus into memory in one query before embedding
  anything - fixed with bounded internal chunking).
- **Real differentiating application, not generic "AI search"**: once
  this and Phase 8's taxonomy population exist, cross-*tradition*
  comparative search becomes possible - this corpus already spans
  multiple scholarly traditions (Deobandi-leaning via Jibreel, Salafi/
  Ahle Hadith via Shamila Urdu, general Sunni via Shamela) in one
  unified database, so "how does a source from each tradition treat
  this same hadith" is answerable from real, owned content - not an AI
  guessing what different schools generally think, which a generic tool
  with no comparable corpus cannot do at all.
- **Desktop GUI wiring: done, live for real.** `SearchScreen` shows
  semantic results in a real "Related pages" section, lazy-loaded on
  first search. Real testing against production found and fixed three
  real bugs, in order: a ~30s network hang on first load (offline env
  vars were set too late - after `sentence_transformers` was already
  imported); a 94.92-second search caused by joining in full page text
  for every one of ~600K embedded rows just to discard nearly all of
  them; and per-row `np.frombuffer`/`np.stack` overhead instead of one
  buffer concatenation. Isolated profiling (not guessing) found the
  real remaining cost was the one-time `sentence_transformers`/`torch`
  Python import itself (~21s) plus model construction (~5s) - not
  fixable in application code, so it's run on a background
  `SemanticSearchWorker(QThread)` instead (same pattern as
  `LibraryImportWorker`): keyword results always appear instantly
  (0.9-2.3s), "Related pages" populates a few seconds to ~36s later
  (once per session) without ever freezing the UI. Verified for real:
  ~36s on the first search, ~8-9s on every search after that at
  ~700K+ embedded pages. `MainWindow` now enables this
  (`enable_lazy_semantic_search=True`) - still a brute-force scan (a
  real ANN index remains the honest long-term answer once the corpus
  is closer to fully embedded), but no longer doing unnecessary work,
  and never blocking regardless of how slow it gets. See CHANGELOG.

### Phase 8 — Maktaba Shamela import + taxonomy GUI: **core work done, full corpus import pending**

Explicitly scheduled by the user to come after Phase 7, not before -
both items below are real and scoped:

- **Maktaba Shamela importer: built, pilot-verified, full corpus not yet
  run.** `F:\المكتبة الشاملة`, 113 GB, 30,662 real books under `Books\`.
  Real architecture (re-investigated properly before building, since the
  originally-documented schema turned out incomplete):
  - Individual `.mdb` files carry **no title/author metadata at all** -
    only `book` (page content; real columns vary per file - some carry
    `seal`, others `hno`/`Sora`/`Aya`/`na` - read dynamically, not
    assumed) and `title` (TOC headings). Real per-book metadata lives in
    a separate catalog, `book_index.db` - despite the `.db` extension
    this is plain SQLite (no COM/OLEDB needed for it), keyed by
    `shamelaID` (matches each `.mdb`'s filename stem, not the catalog's
    own `id` or its stale `filePath`). Author coverage is honestly sparse
    (7,032 of 36,042 catalog rows have a real author name).
  - A single `.mdb` can be a genuine multi-volume work - `book.page`
    resets per `book.part` (confirmed: an 8-part file with 8
    independently-numbered page ranges). The importer splits these into
    one real `Book` per part and reuses the existing Series/VolumeNumber
    grouping (`model_volumes`, now safely re-runnable as a post-import
    backfill, not just a one-time migration) rather than building a new
    grouping mechanism.
  - `title.id`/`title.sub` are not a reliable unique parent link (the
    same `id` recurs across different `lvl`s in real data) - the chapter
    hierarchy is built from `lvl` alone via a level-based stack instead.
  - A `book.id` row is closer to a paragraph than a page - real pilot
    data showed ~12% of rows sharing a page number with another row.
    Same-page rows are merged into one `Page` (content joined in
    reading order), so the existing paragraph-backfill pass picks up
    real sub-page structure automatically, same as the rest of the corpus.
  - Access mechanism: `Microsoft.Jet.OLEDB.4.0` (32-bit only) via
    PowerShell + ADODB, the same shell-out-to-32-bit-PowerShell shape
    already used for Jibreel's `.mjbx` decryption - every modern
    ACE-based provider refuses these Jet 3/Access-97 files outright.
  - Category mapping deliberately **not** attempted: Shamela's own `cat`
    id has no name lookup anywhere in the source data and is a different
    namespace from this project's `MJCN` system - mapping it in would
    silently corrupt `Categories`/`CategoryTaxonomy`.
  - **Pilot run** (30 real files from `Books\0`, per user's explicit
    "pilot first" scope decision): 47 real books (multi-volume splits
    included), **0 read failures**, 5 real Series correctly grouped
    (e.g. Tafsir Ibn Kathir's 8 volumes, Tafsir al-Khazin's 7), spot-
    checked page content/chapter hierarchy against the real source by
    hand. `verify_database_cli.py` against the pilot database: **0
    errors, 0 warnings**. Full ~30,662-book corpus import is a
    deliberately separate, later step - not run yet.
- **Taxonomy population: done, four dimensions.** `TaxonomyRepository`
  populates "subject"/"author" from the already-normalized
  `CategoryTaxonomy`/`Authors` tables, and "language"/"publisher"
  directly from `Books` - idempotent, verified for real against
  production: **691 subject terms, 650 author terms, 3 language terms,
  679 publisher terms, 14,046 book-subject links, 4,466 book-author
  links, 5,212 book-language links, 5,171 book-publisher links**. See
  CHANGELOG (includes a real perf bug found and fixed - bulk linking,
  not one connection per book, and a real term-matching bug found and
  fixed - `get_or_create_term` used to match by display text instead of
  `StableKey`, silently collapsing 43 of 691 real subject categories
  that share Name text under different parents into one wrong term;
  fixed, backfilled, and now guarded by a `DatabaseVerifier` uniqueness
  check). The other five dimensions (madhhab, region, personality,
  event, tag) have **no real source data anywhere in the current
  schema** - re-verified directly against the live database, not
  assumed: no matching column, free-text field, or category text exists
  for madhhab/event/tag/personality; region has only a crude, unstructured
  signal (city/country names embedded in ~20-30% of `Books.Publisher`
  free text) that would need real text-extraction work, not just wiring.
  Left empty and documented honestly rather than filled with fabricated
  or unverifiable low-confidence data - not part of this pass.
- **Taxonomy browsing GUI: done.** New standalone `TaxonomyBrowserScreen`
  rail entry (`main_window.py`, `rail-taxonomy`), following
  `DuplicateManagerScreen`'s DI-with-real-defaults constructor pattern and
  `SearchScreen`'s `QTreeWidget` tree/search-filter pattern exactly. Real
  dimension selector (populated dimensions selectable; empty ones shown
  disabled with an honest "no data yet" tooltip, not hidden), real
  search-within-taxonomy filter, node click -> real linked books via
  `TaxonomyRepository.list_books_for_term()` bulk-hydrated with
  `BookBrowserRepository.list_books_by_ids()` (the same N+1-avoiding
  method `DuplicateManagerScreen` already uses), real "Read in app"
  wired to the existing viewer via `open_in_viewer_requested`. Degrades
  honestly (no crash, no dimension selectable) against a database that
  hasn't run migration 6 yet. Verified against the real production
  database (smoke-tested end to end) and with 8 new pytest-qt tests.

**Phase 8 status: complete, including the full corpus import.** The full
Shamela import ran to completion: 30,662 real files processed, 119
failed to read (malformed source files, ~0.4%), **90,076 books
imported**, 5,889 Series correctly grouped. `data/books.db` grew from a
14,901-book baseline to **104,865 books** (post a safe 112-row
empty-content-stub cleanup) across all 10 libraries. Two real, distinct
data-quality issues were found and fixed while verifying the result at
this new scale (not part of the import itself, both real, both
documented in CHANGELOG):
- `model_volumes()`'s title-regex grouping can merge two *unrelated*
  source files that happen to share a title into one bogus "series"
  (confirmed directly against a raw `.mdb`) - `multi_volume_series.csv`
  now flags this via `SourceFileCount`/`Confidence` rather than trusting
  every apparent gap.
- `DuplicateCandidateRepository.detect_and_store()` was cross-library
  only, missing within-library duplicates entirely - extended to also
  detect same-library Title+Author matches, then batch-scored all 2,132
  resulting candidates against real page content
  (`BookComparisonRepository.compare()`): 73 are ~100% identical
  (near-certain true duplicates, action pending explicit approval - this
  is a real-data-deletion decision), 52 are confirmed different books
  despite matching metadata (safe to dismiss), 2,004 have no
  page-number overlap to compare (inconclusive by this method, not
  necessarily non-duplicates).

### Phase 8.5 — Post-import data quality: duplicates, series accuracy, storage: **in progress**

Inserted out of the main 1-20 sequence (no renumbering, to avoid the real
risk of breaking the many existing cross-references to Phase 9-20 above)
- runs alongside/interleaved with Phase 9 rather than blocking it, since
it's maintenance on the Phase 8 corpus, not a feature phase. Real items
found investigating the corpus at its new 104,865-book scale, each
tracked individually since most touch real production data and need an
explicit go/no-go, not a bulk pass:

- **FTS index storage overhead**: **partially done.** `data/books.db`
  was ~110GB; real page/paragraph/footnote/book text only accounts for
  ~25GB of that. `PagesFTS`/`FootnotesFTS`/`BooksFTS` already use FTS5
  external-content mode correctly (no duplication) - not the problem.
  Migration 16 (`_drop_unused_paragraphs_search_index`) dropped
  `ParagraphsFTS`/`ParagraphsFTSNormalized`, confirmed unused by any real
  search path - applied to production, **5.96GB reclaimed** (pending a
  `VACUUM` to shrink the file itself, deferred until there's enough free
  disk space to safely run it - a 168GB database needs roughly double
  that in free space during `VACUUM`). The bigger remaining piece - the
  `PagesFTS`/`FootnotesFTS`/`BooksFTS` *Normalized* variants (the default
  tolerant-search path) genuinely storing their own text copy because
  `SqliteBookSearchRepository` calls `snippet()` directly against them -
  is scoped but **not started**: needs a real code change (contentless
  FTS5 + computing snippets from the original table instead, with a
  length-preserving normalization pass so match positions still map
  correctly onto the original text). Real, buildable, but touches the
  single most-used code path in the app - planned as its own careful
  milestone, not rushed in. **Explicitly deferred to a later phase
  (tentatively ~Phase 13) per direct instruction** - not urgent (search
  already works correctly today, this is a storage optimization only;
  no user-facing behavior depends on it), and disk pressure that made it
  attractive is temporarily resolved (see the D:/F: cleanup note in
  CHANGELOG - both drives back above 200GB free as of this session).
  Revisit once a dedicated session is warranted; measure actual
  reclaimable space first before committing real effort.
- **Act on the 73 high-confidence (~100% content-identical) duplicate
  pairs**: **73 of 73 done.** 68 resolved automatically with explicit
  approval of the exact policy first ("keep whichever side has more
  pages," not "always delete the flagged side" - that would have deleted
  the better copy in 9 of the 73 cases). The remaining 5 (two transitive
  chains) needed real human judgment, not a safe inference - resolved
  2026-08-05 with the user directly reviewing each chain's real
  page-count/source data. `data/books.db`: 104,865 -> 104,793 books;
  zero orphaned rows verified across every referencing table afterward;
  full backup + human-readable list in `docs/duplicate_analysis/`
  (including the manual-review resolution log). See CHANGELOG.
- **PDF-archive stub duplicates (Maknoon vs. Jibreel)**: **done** (see
  CHANGELOG) - the `NO_COMMON_PAGES` scoring bucket (2,004 rows,
  previously left as "unverified") turned out to be a real, distinct,
  high-confidence pattern: the same PDF collection cataloged twice under
  "Maktaba Al-Maknoon (PDF Archive)" and "Maktaba Jibreel (PDF Archive)"
  (2,002 of 2,004 pairs byte-identical filenames). 2,003 Jibreel-side
  stub duplicates removed per explicit user decision, Maknoon side kept;
  `data/books.db`: 104,793 -> 102,790 books; full backup + before/after
  audit report in `docs/duplicate_analysis/`.
- **Page-count-corroborated same-library/cross-library duplicates**:
  **done** (see CHANGELOG) - the two remaining analysis files grouped
  books by title text alone (no author/page-count corroboration),
  confirmed directly to be dangerous (one group falsely clustered 4
  genuinely different real editions of "أحكام أهل الذمة" as
  "duplicates"). Re-scored by sub-clustering on exact real page count
  (excluding anything with real `VolumeNumber`/`SeriesID` data) instead
  of bulk-processing the weak signal - 304 real extra copies removed
  per explicit user decision; `data/books.db`: 102,790 -> 102,486 books.
- **Dismiss the 52 confirmed-different candidates**: **done.**
  `DuplicateCandidates` gained a real `Status` column
  (`pending`/`dismissed`), preserved across `detect_and_store()` re-scans;
  the Duplicate Manager screen's session-only "Skip" is now a persistent
  "Dismiss". Applied to production: the 52 real `LIKELY_DIFFERENT_BOOK`
  pairs are dismissed, 2,080 of 2,132 candidates remain pending. See
  CHANGELOG.
- **Stale backup decision**: **done.** The ~24GB pre-Shamela backup
  (missing ~90k books and the recent dedup pass - not a usable restore
  point for the current corpus) was deleted; a fresh backup of the
  current, post-dedup database was created via `database_backup_cli.py`
  (`data/backups/books_backup_20260802_074832.db`, ~156GB, SQLite's
  online backup API - safe to take against a live database).
- **Shamela title-mismatch bug: root cause confirmed.** The Shamela
  source library became reachable again at `D:\المكتبة الشاملة`
  (new-machine gap resolved). Queried `book_index.db` directly for the
  exact `shamelaID`s behind the confirmed mismatches (SeriesID 2216,
  414, plus two more found this session, 2054 and 781): the real
  catalog **already contains these exact wrong titles** against these
  exact IDs. This project's importer/matching code is reading the
  catalog correctly - the bug is genuine upstream data noise in
  Shamela's own crowd-sourced catalog, not a bug in
  `shamela_book_reader.py`/`shamela_catalog_reader.py`. Nothing to fix
  in this project's code for this specific issue; not otherwise
  algorithmically detectable, since individual `.mdb` files carry no
  independent title of their own to cross-check against (confirmed
  architectural fact from Phase 8).
- **`missing_volumes_availability.csv` web research**: **done, real
  findings, not "not yet researched" placeholders.** First re-verified
  all 35 "plausible" (small-gap) series directly against the real
  catalog now that it's reachable: **28 of 35 have a real title with
  zero mismatch** (exact match against `book_index.db`); the other 7
  simply have no catalog entry at all (a different, already-understood,
  honestly-handled case - falls back to the bare filename as title, not
  a wrong title). So this list was safe to research, unlike the 53
  large-span series (still flagged suspicious, not researched this
  pass - matches the same pattern confirmed for 2216/414 above).
  - Researching the 28 surfaced a **second real finding**, checked
    directly against `book_index.db`'s `bookInfo` field (not guessed):
    most of the 28 aren't "missing book volumes" in the way the task
    assumed. **6 aren't real gaps at all** - the catalog states the
    work has only 1 real part, or (one case) the title itself says the
    original work only ever excerpted parts 1 and 3, never part 2.
    **2 are journal-serialized**: the catalog states outright
    `[ترقيم الكتاب موافق للمطبوع، ورقم الجزء هو رقم العدد من المجلة]`
    - the "volume number" is a *journal issue number* (مجلة الجامعة
    الإسلامية), not a book volume - a different, more specialized
    research target than "find book volume N." **1 has no real title**
    (Shamela's own internal orphaned-file placeholder, "منوع", not a
    real book). That leaves **4 confirmed genuine gaps** (catalog
    states a real total part count matching the claimed gap): Ibn
    al-Jawzi's *al-Muntazam* (10 vols, missing 2-4), *Tarikh Ibn Ma'in*
    (two separate real 4-volume uploads, both missing vol. 2), and a
    real 8-volume *Muwatta Malik* edition (missing vols. 6-7) - real
    web availability found for 3 of these 4 (the *Muwatta* edition
    confirmed with all 8 volumes on archive.org). The remaining 16 of
    28 stay genuinely ambiguous (catalog gives no part-count metadata
    either way) - not resolved further this pass.
  - Full per-series results (Availability + Notes columns) written to
    `docs/book_inventory/missing_volumes_availability.csv` (gitignored,
    local only - see CHANGELOG for the full breakdown).
- **Series false-merge regex fix**: **done.** `model_volumes()` now
  groups by `(base_title, shamela_source_key)` instead of `base_title`
  alone - every non-Shamela book keeps exactly its prior behavior
  (`shamela_source_key` is always `None`), while two different Shamela
  `.mdb` files whose titles happen to regex-collide get their own,
  deterministically-named `Series` instead of being silently merged.
  Turned out much bigger in real scope than the original ~36-series
  estimate: dry-run verified against production first (rolled back, not
  guessed) - **5,889 -> 6,594 series**, 68,159 books' `SeriesID` count
  unchanged (pure re-grouping, zero books lost or gained). Confirmed
  correct, not over-aggressive, by checking real cases: "المحلى" splits
  into a genuine 16-volume and a genuine 10-volume edition (each
  independently numbered 1..N, not one garbled series with duplicate
  volume numbers) - same pattern for *Sahih Muslim*, *Sunan Abi Dawud*,
  *al-Mabsut*. The bug hit the corpus's most-referenced classical texts
  hardest, since those are exactly the ones re-uploaded as multiple real
  editions in a crowd-sourced library. Also found and fixed a related
  gap while applying this: a Series left with only 1 real member (a
  sibling volume deleted elsewhere, e.g. by real duplicate-removal, with
  nothing reconciling Series membership) is now self-healed on any
  `model_volumes()` re-run, not just at first-creation time - closed one
  real pre-existing case this surfaced (1 stray book, `معرفة الصحابة
  لأبي نعيم` part 3). Applied to production, verified: 0 orphaned
  `Books.SeriesID` references, 0 under-populated Series rows. 3 new
  tests. See CHANGELOG.
- **Push to GitHub**: `origin` is configured
  (`github.com/hamzaabbasi1992-ctrl/IslamicResearchHub`) but the local
  branch is well ahead, unpushed - relevant for the new-machine migration
  the user is planning. Not started.

### Phase 9 — Accessibility, engagement, and AI research tools: **in progress**

Added at the user's explicit request. Five real, distinct items - grouped
into one phase because they're all later-stage, all optional relative to
the core search/browse/read experience, and several build on each other
(TTS underlies both voice search and AI audio summaries). Useful, but
worth being honest that most of this is commodity value-add (any AI
wrapper on any document pile could offer TTS/voice search), not a
differentiator the way Phase 6/10's items are:

- **Text-to-speech, Arabic/Urdu/English**: **Milestone 1 done** - read the
  current page aloud in `ViewerScreen`, one default local voice per
  language, off by default behind a real Settings toggle. Local model
  chosen and verified for real (not assumed): `facebook/mms-tts-{ara,
  urd-script_arabic,eng}` (Meta's MMS project) - the Urdu risk this item
  originally flagged is resolved for real, since MMS covers Urdu under the
  same architecture/checkpoint family as Arabic, unlike Piper (no
  confirmed Urdu voice). Real, measured synthesis speed: ~3.1x realtime on
  CPU - a real ~2,000-character page took ~79s end-to-end against a real
  production book, confirmed reaching `PlaybackState.PlayingState` in Qt's
  own media backend. Found and fixed two real issues along the way: raw
  structural markup in ~471,000 pages (mostly Maktaba Jibreel) that would
  have been read aloud literally, and a real Windows file-lock bug turning
  the page mid-playback (caught by the feature's own tests, not manual
  testing). See CHANGELOG.
  - **Chunked/streaming synthesis: done** (see CHANGELOG). Page text now
    splits into ~320-character chunks (real line/heading boundaries first,
    then Arabic/Urdu/Latin sentence punctuation, then a word-boundary hard
    cut), synthesized and played progressively - the real ~79s-of-silence
    wait for a long page is now ~10-15s before sound starts, with
    real auto-advance between chunks. A later chunk failing mid-page keeps
    and plays the earlier successfully-produced chunks (log-only, no new
    UI - a deliberate scope choice, worth revisiting if real users hit it
    often).
  - **Deferred to a later milestone, not silently dropped**: multiple
    voices, adjustable speed, male/female options, separate pronunciation
    handling for classical Arabic recitation-style text vs. conversational
    Urdu/English, cloud TTS upgrade, `PdfViewerScreen` support (blocked on
    OCR - PDF-only books have no extracted text at all).
- **English-language books**: not a technical feature - every library
  imported so far (Jibreel, Al-Maknoon, Islam, Shamila Urdu, Shamela) is
  Arabic/Urdu. This needs its own Phase-1-style source investigation
  (find real English Islamic-book collections, check format/scale/
  overlap) before any importer can be scoped. **Investigation started,
  deliberately paused**: `islamhouse.com` has a real, documented public
  API (developers.islamhouse.com, MIT-licensed client code, content
  requires attribution) - a genuinely legitimate candidate, but the
  first *network-API* source this project would import from (every
  library so far has been local files), needing a registered API key
  from the user plus real architecture decisions (rate limits, one-time
  vs. incremental sync) before building. Explicitly deprioritized below
  Phase 6's readiness work per direct instruction - not resumed yet.
- **Suggestions / questions / ratings / community feedback**: scoped
  down to what this project's real architecture supports - a
  single-user local desktop app, not a multi-user backend. **Personal
  per-book rating: done** (migration 12, `BookRatingRepository`, wired
  into `SearchScreen`'s detail panel - see CHANGELOG). Notes/questions,
  tagging, a "suggested for you" panel, and any real vote/moderation
  flow are real, separate scope for whenever (if ever) this project
  gains actual multi-user/community infrastructure - not assumed to be
  the same size as the rating slice just shipped.
- **Voice search with AI**: **Milestone 2 done** - a mic button in
  `SearchScreen`'s query row records a spoken query and feeds the real
  transcript into the existing keyword search pipeline, off by default
  behind a real Settings toggle. Local model chosen and verified for real:
  `faster-whisper` (CTranslate2-based Whisper, multilingual `small`,
  CPU/int8) - a real, deliberate new dependency ecosystem (not the `tts`
  extra's `torch`/`transformers` stack), chosen because voice search's
  whole value is being faster than typing. Real round-trip accuracy
  confirmed with realistic query-length phrases (6-7/7 words correct per
  language). Found and fixed three real bugs along the way (see
  CHANGELOG): an already-shipped fresh-install-breaking bug in TTS's own
  offline-loading code, and two crashes/dead-ends surfaced only by this
  feature's own end-to-end test against the live production database - a
  pre-existing, voice-search-unrelated title-search crash on any
  punctuated query, and Whisper's own auto-added punctuation defeating
  search entirely even once the crash was fixed. Cloud STT remains a
  possible optional upgrade per the Architecture policy above, not needed
  yet.
  - **Deferred to a later milestone, not silently dropped**: continuous/
    hands-free listening (press-to-record only), a confirm-before-searching
    step, language hinting, voice search inside the viewer screens, cloud
    STT, a waveform/VU-meter, and query-shaping the transcript (e.g. spoken
    "surah two ayah thirty" into a citation-shaped query).
- **NotebookLM-style AI research workspace** (summaries, audio
  overviews, visual reports): a user selects a scope - one book, several
  books, or a whole taxonomy-defined collection - and generates a book/
  chapter/topic summary, or a multi-voice audio-overview-style
  discussion using the TTS item above. Real AI-generated *video* is a
  materially bigger, separate undertaking - see Phase 17, not assumed
  to be the same size as the rest of this phase.
  - **The summarization piece: Milestone 1 done**, delivered as part of a
    broader "AI Agent" capability (see CHANGELOG) - real, cloud-LLM-backed
    Q&A grounded in real book content with real citations, natural-
    language search shortcuts, and on-demand book/chapter summarization,
    all via one real tool-calling loop over this library's own existing
    search/retrieval. Multi-provider (Anthropic/OpenAI/Gemini) from day
    one, off by default. Multi-voice audio-overview discussions and
    visual reports remain not started.

### Phase 10 — Knowledge graph and encyclopedia builder: **in progress**

**Real foundational step already done, ahead of the rest of this phase**:
permanent paragraph-level citation IDs - migration 13 (`Paragraphs` +
`ParagraphsFTS`/`ParagraphsFTSNormalized`, backfilled for real against
all 15,162 books), migration 14 (`Pages.HadeesNumber`/`AyahNumber`,
previously-dropped real citation numbers now captured), migration 15
(`BooksFTS`/`BooksFTSNormalized`, bm25-ranked title/author search,
replacing the old unranked `LIKE` scan), and
`BookBrowserRepository.get_volume_siblings()` +
`shared/citation_formatting.py::format_citation()` for the "Book X,
Volume Y, Page Z, Paragraph N" display format. See the CHANGELOG entry
"Milestone 1 resumed: permanent paragraph citation IDs + search
foundation" for full detail. This is exactly the addressable-citation
infrastructure the citation graph/knowledge graph items below need - a
`Paragraphs.ParagraphID` is the natural foreign key for a future
passage-level entity-link table (today's `BookTaxonomyTerms` only links
at whole-book granularity). Deliberately did **not** start on Waqi'at
extraction, entity population, or any AI-driven step yet, per your own
stated preference to build the non-AI data foundation first.

The user proposed a much larger 18-phase "AI Research Operating System"
vision in one message (semantic search, NotebookLM workspaces, TTS,
translation, encyclopedia generation, knowledge graphs, isnad/citation
tracing, quizzes, an API platform, mobile apps, and more), then
explicitly asked for a version that prioritizes what's genuinely unique
to this project over generic AI-wrapper duplication. This phase is
where that reprioritization matters most: it now foregrounds the real
differentiators (only possible because of this project's actual,
already-unified data), ahead of the more generic knowledge-graph/
encyclopedia framing. Four further items (contradiction/knowledge-gap/
preservation detectors, cross-language search) were added afterward
from a follow-up "unique advantages" discussion, each confirmed to
build on infrastructure this phase or an earlier one already produces,
not new data-collection problems of their own:

- **Citation graph between owned books**: **Milestone 1 done, real full
  scan completed** (see CHANGELOG) - detects when one book's text
  literally names another book's title that's also in this corpus,
  exact-literal-phrase matching only (no author-mention detection yet,
  no general NER). Real yield from the actual completed scan against the
  full 104,797-book production database: **329,202 candidates**, 44,310
  citing books, 13,586 cited books - far more than the `--sample`-based
  estimate predicted. Running the real scan surfaced and fixed two real
  bugs the sample run never hit: a `Pages.PageNo IS NULL` crash at the
  final write step, and an app-crashing `sqlite3.OperationalError: too
  many SQL variables` in `list_books_by_ids()` at this real candidate
  count (now batched). `CitationManagerScreen` (mirrors the Duplicate
  Manager screen) now pages through results 100 at a time - loading all
  329,202 rows into one table was itself unusable, confirmed directly.
  Deferred, not silently dropped: surfacing confirmed links inside the
  reader/book-detail panel (real UI design work better done once real
  detection-quality data exists to design around), author-mention
  detection, general NER-based knowledge graph items below.
- **Waqiat (event) extraction**: **Milestone 1 done** (see CHANGELOG) -
  book-by-book, on-demand (never a corpus-wide sweep - real cost math
  makes that tens of thousands of dollars for the whole library), a real
  "Extract Events" button in the reader chunks the open book (chapter-
  sized when real TOC structure exists), shows a real cost estimate
  before spending anything, then extracts structured events (title,
  dates, location, background, summary, key figures, a real verbatim
  quoted excerpt, a real citation) via the existing AI Agent
  infrastructure. Stored as 3-state (`pending`/`confirmed`/`dismissed`)
  candidates - deliberately stronger review than citations/duplicates,
  since an extracted event asserts real historical facts an LLM could
  hallucinate. New `EventManagerScreen` for review. Also shipped: a
  shared "AI unavailable, here's why and how to fix it" popup, used by
  this button and retrofitted onto the already-shipped AI Agent Ask box.
  Deferred, not silently dropped: cross-book event merging/deduplication
  (the "Battle of Badr mentioned in 20 books becomes one master event"
  step from the original Knowledge Extraction Engine discussion) - a
  real, separate step once enough books have real extracted candidates
  to merge.
- **Structured narrator/isnad database - safe version**: **Milestone 1
  done** (see CHANGELOG) - mirrors the Waqiat architecture exactly:
  book-by-book, on-demand, a real "Extract Narrators" button in the
  reader with a real cost estimate confirmed first, extracting
  structured narrator mentions (name, alternate names, kunya/nasab,
  any generation the text itself states, hadith reference, a verbatim
  quoted excerpt, a real citation) via the existing AI Agent
  infrastructure. **Without the AI ever rendering an authentication
  judgment** - enforced in the extraction system prompt itself (tested
  directly, not just documented) and reinforced by a visible safety
  note on the new `NarratorManagerScreen`. Stored as 3-state
  (`pending`/`confirmed`/`dismissed`) candidates, same reasoning as
  `EventCandidate`. This is the real, buildable, safe version of
  "isnad visualization" - deliberately separated from the
  AI-authentication-judgment version, which stays deferred in Phase 20
  as a high-risk item needing real scholarly review first. Deferred,
  not silently dropped: cross-book narrator identity resolution (the
  same name spelled differently across books becoming one entity).
- **Knowledge graph** (general): migration 6's taxonomy schema
  (`TaxonomyTerms` with `ParentTermID` hierarchy, `BookTaxonomyTerms`
  many-to-many, `TaxonomyAliases`) already models this shape of data -
  it's currently empty. Broader relationship data (teacher/student,
  scholar/city) beyond the two differentiators above needs its own NER
  extraction step - a genuine R&D step, not just a UI, and should be
  scoped for real once attempted, not assumed to work.
- **Encyclopedia builder**: a natural extension of Phase 8's taxonomy
  GUI item, not new scope - once real taxonomy data exists (subjects,
  personalities, places, events), auto-assembling "every book/page
  linked to this term" into an encyclopedia-style page is a direct
  application of data that will already be there. Depends on Phase 8's
  taxonomy population happening first. Real scope spans every taxonomy
  dimension already designed for this in migration 6 - prophets and
  companions (biography, teachers, students, narrations, linked books),
  places (with maps once geographic data exists), and general topics
  (animals, plants, medicine, trade, ethics, etc.) - each becomes an
  auto-assembled page from real linked content, not hand-written.
- **Visualizations** (mind maps, timelines, relationship/topic graphs,
  family trees, maps, infographics, flowcharts): a rendering layer on
  top of the same knowledge-graph data above, not a separate data
  problem - scoped together with it, not before it. Different chart
  *types* over the same underlying graph/timeline data, not different
  data problems - built as one flexible visualization layer, not one
  bespoke feature per chart type.
- **Contradiction detector**: flag passages where the same author's
  work appears to say different things in different places, for a
  researcher to evaluate - explicitly a *flag*, not an AI verdict that
  a contradiction exists, same evidence-not-judgment discipline as the
  citation graph above. Needs the same content-linking infrastructure
  (real page text already indexed, semantic search from Phase 7) rather
  than new data collection.
- **Knowledge gap detector**: **done** (see CHANGELOG) - new
  `KnowledgeGapScreen`, per dimension (subject/author/language/
  publisher - the four Phase 8 has actually populated), lists real
  low-coverage terms ("only N books cover this") sparsest-first, with a
  real adjustable "fewer than N books" threshold. Pure query + filter
  over `BookTaxonomyTerms` counts - no AI, no new data collection,
  confirming the original scoping note. Not yet done: a "no English
  references" type cross-dimension finding - the current version reports
  per-term gaps within one dimension at a time, not cross-dimension
  correlations; a real, separate, smaller follow-up once useful.
- **Digital preservation reports**: **Milestone 1 done** (see
  CHANGELOG) - new `PreservationReportScreen`, generated on demand via
  a background worker (real, measured cost against the full production
  corpus: ~28 minutes/1696s, genuinely citation-detection territory,
  not a rough guess). Surfaces pending duplicate count (linking to
  Duplicate Manager, not re-implementing review) and real
  incomplete/unreadable books (no text and no PDF fallback either way)
  - both extensions of already-built detection
  (`DuplicateCandidateRepository` from Phase 2,
  `PdfMatchCandidateRepository`'s own stub thresholds reused, not
  redefined). Real yield: 3 pending duplicates, 1,565 incomplete books
  (all sparse/heading-only with no matched PDF - zero real zero-page
  anomalies found). **Corrupted/damaged file tracking confirmed not
  buildable as "just a report"**: investigated directly - import-time
  failures are only ever a transient log line today, nothing persisted
  post-import to query; would need new schema across every importer, a
  real, separate, bigger undertaking - deferred, not silently dropped.
- **Cross-language conceptual search**: a query typed in Urdu should be
  able to surface relevant Arabic-only results (and vice versa) - a
  real gap distinct from Phase 12's paragraph translation, since this
  is about *search* finding conceptually related content across
  languages, not translating found content afterward.
  **Checked for real, not assumed - confirmed broken as currently
  deployed** (2026-08-06): ran real Arabic queries against the live
  production index (1,695,366 embedded pages: ur 1,031,696 + "Urdu"
  282,641 + ar 175,727 + unlabeled 205,301 - Arabic is a real 10%+ of
  the index, not negligible). A real Arabic query about divorce
  jurisprudence (أحكام الطلاق في الفقه الإسلامي) returned **zero**
  Arabic-language results in the top 50; a fasting query (فضل الصيام)
  returned exactly 1 of 50, ranked #35. `paraphrase-multilingual-MiniLM-L12-v2`
  (the model already in production use for same-language semantic
  search) does not provide usable cross-lingual retrieval here as
  currently wired - Urdu content systematically dominates results
  regardless of query language, likely the model's imperfect
  cross-lingual alignment compounded by the corpus's real ~6:1
  Urdu:Arabic embedded-page imbalance. Real follow-up work needed
  before this is buildable: language-aware re-ranking/boosting, a
  fairness-weighted merge across per-language result pools, or
  evaluating a different multilingual model - not attempted this pass,
  scope not yet sized.

### Phase 11 — AI research assistant: **Milestone 1 done**

Goes beyond search: a user asks a real comparative question ("how did
the four madhhabs differ on raising the hands in salah?") and the
assistant gathers real evidence across the corpus (via Phase 7/10's
semantic search and knowledge graph), quotes original passages with
real page references, and presents differing positions side by side.
**Hard requirement, not optional**: every claim must link back to a
real, openable page in a real book - no unsourced/unverifiable output.
Comparing scholarly positions is exactly the kind of feature flagged
earlier as carrying real accuracy risk in a religious-scholarship
domain - this phase's output is explicitly evidence-plus-citations, not
the assistant rendering its own verdict on which position is correct.
Commodity-level feature (any AI-document tool could offer something
like this) - real value comes from Phase 7's cross-tradition corpus and
Phase 10's verified citation graph underneath it, not from this layer
itself being novel.

**Milestone 1: done** (see CHANGELOG) - a "Compare scholarly positions"
mode added to the already-shipped AI Agent's Ask box, not a separate
system: same real tool-calling loop, a second system prompt requiring
real citations per position and explicitly forbidding a verdict on
which is correct. Deliberately does **not** wait on the rest of Phase
10's knowledge graph/encyclopedia work - the underlying tool-calling
loop already does real retrieval (`search_books`/`semantic_search_books`/
`get_book_pages`) regardless of whether a formal knowledge graph exists
on top of it; a real citation graph or populated taxonomy would improve
*findability* of positions, not gate whether comparison itself works.
**Not yet live-tested with a real API key** - same open item as AI
Agent Milestone 1 itself, needs the user to try a real comparative
question. Deferred, not silently dropped: any UI surfacing of
positions beyond plain text (e.g. a real side-by-side visual layout,
not just prose in the existing answer area) - a real, separate
follow-up once the underlying comparison quality itself is verified
against a real provider.

### Phase 12 — Translation engine: **Milestone 1 done**

Real per-paragraph translation chain: original Arabic → Urdu → English,
plus word-by-word breakdown, grammar notes, and root-word analysis
(particularly valuable for Arabic morphology). Local translation model
by default, cloud upgrade optional, per the Architecture policy above;
quality/accuracy needs a real check before this is presented as
authoritative either way, same caveat as Phase 11.

**Milestone 1 (done)**: "Translate to English" for a selected passage,
scoped down deliberately from the full chain above - a real, working
Arabic/Urdu → English path on real local models first, before layering
on Urdu as a target, word-by-word breakdown, or grammar notes. Local by
default per the Architecture policy: `MarianTranslator`
(`Helsinki-NLP/opus-mt-ar-en` / `opus-mt-ur-en`, one small ~300MB model
loaded lazily per source language, mirrors `MmsTtsSpeaker`'s exact
lazy-load shape) behind a new `TextTranslator` Protocol
(`PageTranslationService`). No direct Arabic↔Urdu pair exists in
Helsinki-NLP's catalog - pivoting through English (ar→en→ur) would
compound translation error and isn't a real, evaluated capability yet,
so Urdu-as-target is explicitly out of scope for this milestone, not a
missed case. New "Translate to English" context-menu item in the Viewer
(gated by a real Settings toggle, `TRANSLATION_ENABLED_KEY`, same
opt-in-because-it's-a-model-download reasoning as TTS/voice search),
shows a real read-only dialog (original + translation + an honest
disclaimer that this is a real local-machine translation, not a
substitute for a qualified human translator on anything touching a
legal/religious ruling). **Not yet live-tested with the real model** -
built and automated-tested (fake translator, same technique as
`_FakeTtsSpeaker`) against the exact same architecture MMS-TTS already
proved out for real; the actual ~300MB-per-language download and real
translation quality haven't been checked by a human yet.

### Phase 13 — AI reading assistant: **Milestone 1 done**

The in-reader interaction layer: highlight text while reading, then
ask the AI to explain, compare, translate (Phase 12), or summarize it,
and save the result as a note or bookmark (Phase 5's bookmark schema
already exists as a foundation). This phase is the UI/interaction
layer specifically - it calls into Phase 11 (research assistant) and
Phase 12 (translation) rather than re-implementing their logic, so
there's one real place each capability lives, not several.

**Milestone 1 (done)**: "Explain this passage" - select real text while
reading, right-click, get a real AI explanation of that specific
passage (meaning, context, significance), grounded via the same
tool-calling `AiAgentService` as Phase 11, with its own system prompt
(`AiAgentService.explain_passage()`, mirrors `compare_positions()`'s
exact shape) that explicitly forbids presenting the explanation as a
fatwa or authoritative ruling - a reading aid, not scholarly guidance.
Translate (Phase 12) already existed as its own context-menu item;
"Compare"/"Summarize" from the passage above and "save as a bookmark"
are still out of scope for this milestone - "save as a note" is in
(the result dialog's "Save to Research Notes" button reuses the exact
same `show_save_to_notes_dialog` flow the reader's own text-selection
menu already used). Routed through `MainWindow` (owns the real AI
Agent service/pre-flight check, same split as Extract Events/
Narrators), not handled locally in `ViewerScreen` like TTS/translation
are, since those use their own separate local models.

**Real live-key verification, 2026-08-06**: while building this
milestone, the user's real Gemini API key was tested end-to-end for
the first time (see `project_ai_agent_milestone1_status` memory) -
found and fixed two real, sequential Google Cloud configuration gaps
(API not enabled on the project; then the key's own API restrictions
blocking it) that were unrelated to any code in this repo. Real
conversational-loop verification (tool-calling against the actual
corpus) is still pending final confirmation once the key restriction
fix takes effect.

### Phase 14 — Personal research workspace: **Milestone 1 done**

Folders, collections, saved searches, saved AI conversations, and
export tools, built on top of Phase 5's existing bookmarks/recent-books
tables rather than replacing them. Real new scope: organizing
bookmarks/notes into named research projects and exporting a
collection (with real citations) as a document.

**Milestone 1 (done)**: real named Collections, additive on top of
Phase 5's bookmark schema rather than replacing it (migration 17:
`Collections`/`CollectionItems`, deliberately no foreign key to
`BookBookmarks` - a page can join a collection without first being
separately bookmarked). New `CollectionRepository` (create/rename/
delete/list collections, add/remove/list real items), a new
`CollectionsScreen` (create/rename/delete, view a collection's real
items, remove an item, open one in the Viewer), a real "Add to
Collection" button in the Viewer's toolbar (pick an existing collection
or create one inline), and a real .docx export
(`research_notes/collection_export.py`, reusing the same python-docx
dependency `docx_writer.py` already uses) with each item's real page
content and citation. Saved searches and saved AI conversations are
still out of scope for this milestone, not missed - Collections was the
concrete, well-scoped first piece.

### Phase 15 — Educational features: **Milestone 1 done**

Quizzes, flashcards, MCQs, spaced-repetition-style revision, lesson
plans, and a "teaching mode" view. Real dependency: question generation
needs to be grounded in real page content (same sourcing discipline as
Phase 11), not free-floating AI-generated trivia.

**Milestone 1 (done)**: real flashcard generation from one book's real
page content, mirroring Extract Events/Narrators' exact shape -
`AiAgentService.generate_flashcards()` (own system prompt, strict JSON
array output), `FlashcardCandidateRepository` (three-state pending/
confirmed/dismissed review, same reasoning as EventCandidate/
NarratorCandidate: a generated flashcard asserts a real fact an LLM
could hallucinate), a new Flashcards rail screen (review/confirm/
dismiss candidates), and a real Study mode - a sequential flip-through
of only the *confirmed* flashcards, never an unreviewed or dismissed
one. MCQs, real spaced-repetition *scheduling* (interval tracking, due
dates - Study mode here is just sequential review, not SRS), lesson
plans, and "teaching mode" are still open within this same phase, not
missed - flashcard generation was the concrete, well-scoped first
piece.

### Phase 16 — AI content generator: **Milestone 1 done**

Produces structured output documents - lecture notes, khutbah outlines,
research-paper drafts, book reviews, comparison tables, citation lists
- from real evidence gathered the same way Phase 11 gathers it. This
phase is the "turn evidence into a formatted document" layer; it
depends on Phase 11 for the underlying evidence-gathering rather than
duplicating it.

**Milestone 1 (done)**: export a real, already-answered AI Assistant
question (Phase 11's `converse()`/`compare_positions()`) as a real
.docx document - `research_notes/ai_answer_export.py`
(`build_answer_document()`/`export_answer_to_docx()`, same shape as
`collection_export.py`), a new "Export Answer" button in the AI panel
that appears once a real answer is on screen and disappears again on a
new question, using the same `QFileDialog.getSaveFileName()` ->
export -> `QMessageBox.information()` pattern as Collections' export.
Deliberately does not gather any new evidence or add new document
types (lecture notes, khutbah outlines, comparison tables, etc.) -
those remain open within this phase, not missed; this milestone proved
the export path end-to-end on the simplest real case first.

### Phase 17 — Multimedia generation: **scheduled after Phase 16, not started**

Extends Phase 9's audio-overview stretch goal into a full multimedia
set: narrated podcasts, whiteboard-style animated explanations,
auto-generated slide decks, and timeline videos. Real AI-generated
*video* (as opposed to audio, already covered by Phase 9's TTS) is a
materially larger, separate engineering undertaking - each output
format in this phase needs its own feasibility check before being
committed to, not assumed to work at the same effort level as the rest.

### Phase 18 — Mobile companion app: **scheduled after Phase 17, not started**

The project's own stated goal already names this ("Windows desktop app
first, Android app later" - see Goal, above) - this phase is that
"later" spelled out for real: an offline mobile library, camera-based
OCR capture, and bookmark/download sync with the desktop app's
database. A materially different platform/tech stack from the current
PySide6 desktop app, not a small extension of it.

### Phase 19 — Developer APIs: **scheduled after Phase 18, not started**

Public APIs (search, translation, citation, book metadata, knowledge
graph, TTS) so other Islamic-research tools could build on this
platform's data. Real prerequisite: everything these APIs would expose
needs to already exist and be trustworthy (Phases 7-12) before it's
worth exposing to outside consumers.

### Phase 20 — Advanced research tools: **scheduled after Phase 19, not started**

The remaining, most research-grade item set in this roadmap - grouped
together because they share one real requirement: **scholarly review as
a hard design constraint, not an afterthought**, given this is Islamic
scholarship, not general-purpose text analysis. (Duplicate-edition
detection and variant-text comparison moved to Phase 6 as real,
buildable-now differentiators; citation-chain tracing and the safe
narrator-database work moved to Phase 10.) OCR confidence heatmaps and
manuscript alignment are comparatively low-risk (they're about
identifying differences, not asserting religious conclusions).
Root-word/morphology search and automatic bibliography generation are
real, buildable NLP tasks with existing tooling to evaluate. **Isnad
(chain-of-narration) AI-authentication and automatic literature-review
generation remain the highest-risk items in this entire roadmap** -
hadith authentication is specialized scholarly work; an AI system that
renders or implies an authentication judgment without rigorous,
expert-reviewed grounding risks presenting unverified or wrong
conclusions as fact. These two sub-items specifically should not ship
without real scholarly review in the loop, not just a disclaimer.

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
