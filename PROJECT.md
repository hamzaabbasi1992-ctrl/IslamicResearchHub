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
- **Full-corpus run: in progress.** The original ~18 hour estimate used
  a smaller, older corpus and an unmeasured throughput guess; the real,
  measured throughput on this machine is ~8.5-8.7 pages/sec (CPU only),
  giving an updated estimate of **~76-78 hours** for all 2,385,159
  pages. Running unbounded in the background per explicit request,
  resumable at any point (migration 9 + the resume/skip logic above).
  A real bug was found and fixed right after starting it (see
  CHANGELOG: an unbounded run tried to load the entire remaining
  corpus into memory in one query before embedding anything - fixed
  with bounded internal chunking).

### Phase 7 — Maktaba Shamela import + taxonomy GUI: **scheduled after Phase 6, not started**

Explicitly scheduled by the user to come after Phase 6, not before -
both items below are real, scoped, but deliberately deferred:

- **Maktaba Shamela importer**: `F:\المكتبة الشاملة`, 113 GB, 30,662
  real books, 99.5% new vs. the existing corpus (would more than double
  it). Investigated, not yet built - see CHANGELOG. **Blocker resolved**:
  the modern ACE engine (ODBC, DAO, and the newer OLEDB provider) refuses
  these Jet 3/Access-97 files, but the older `Microsoft.Jet.OLEDB.4.0`
  provider (32-bit only) opens them correctly - confirmed for real
  against an actual Shamela `.mdb` file (`book` table: id/nass/page/
  part/seal; `title` table: id/lvl/sub/tit, real table-of-contents
  hierarchy). The importer itself is not yet built.
- **Taxonomy dimension browsing/tagging GUI**: migration 6 added the
  general nine-dimension schema (subject, author, madhhab, language,
  publisher, region, personality, event, tag) and `TaxonomyRepository` -
  see CHANGELOG. No data has been migrated into it and no GUI browses it
  yet; both are this phase's real work, not migration 6's.

### Phase 8 — Accessibility, engagement, and AI research tools: **scheduled after Phase 7, not started**

Added at the user's explicit request. Five real, distinct items - grouped
into one phase because they're all later-stage, all optional relative to
the core search/browse/read experience, and several build on each other
(TTS underlies both voice search and AI audio summaries):

- **Text-to-speech, Arabic/Urdu/English**: local/offline TTS (consistent
  with the project's offline-first design, same pattern as the semantic
  search pilot). Urdu is the real risk here - fewer good open-source
  Urdu TTS models exist than for Arabic/English; needs a quality check
  before committing to a specific engine. Real scope includes multiple
  voices, adjustable speed, male/female options, and separate
  pronunciation handling for classical Arabic recitation-style text vs.
  conversational Urdu/English.
- **English-language books**: not a technical feature - every library
  imported so far (Jibreel, Al-Maknoon, Islam, Shamila Urdu, Shamela) is
  Arabic/Urdu. This needs its own Phase-1-style source investigation
  (find real English Islamic-book collections, check format/scale/
  overlap) before any importer can be scoped. Per explicit instruction,
  this investigation happens as part of Phase 8, not before it.
- **Suggestions / questions / ratings / community feedback**: real
  per-book and per-author ratings, notes/questions, tagging, and a
  "suggested for you" panel built on the existing taxonomy/author/
  category data - similar scope to the Phase 5 bookmarks/recent-books
  work. Also covers user-submitted OCR-error reports and correction
  suggestions once OCR exists (see "Not yet scheduled" below) and a
  vote/moderation flow before any user feedback is allowed to change
  what the AI features (Phases 9-19) actually surface - moderation is
  part of this item's real scope, not a later add-on.
- **Voice search with AI**: local speech-to-text (a Whisper-class model
  handles Arabic/Urdu/English) feeding the existing search pipeline -
  no cloud dependency, same local-AI pattern as the embedding pilot.
- **NotebookLM-style AI research workspace** (summaries, audio
  overviews, visual reports): a user selects a scope - one book, several
  books, or a whole taxonomy-defined collection - and generates a book/
  chapter/topic summary, or a multi-voice audio-overview-style
  discussion using the TTS item above. Real AI-generated *video* is a
  materially bigger, separate undertaking - see Phase 16, not assumed
  to be the same size as the rest of this phase.

### Phase 9 — Knowledge graph and encyclopedia builder: **scheduled after Phase 8, not started**

The user proposed a much larger 18-phase "AI Research Operating System"
vision in one message (semantic search, NotebookLM workspaces, TTS,
translation, encyclopedia generation, knowledge graphs, isnad/citation
tracing, quizzes, an API platform, mobile apps, and more). Deliberately
**not** adopted wholesale - most of it is unscoped aspiration with no
real feasibility check yet, several items (automatic encyclopedia
"completeness", AI-compared fiqh positions, isnad-chain analysis, AI
literature reviews) carry real accuracy/harm risk in a religious-
scholarship domain if built without scholarly review as a hard
requirement, not an afterthought, and adopting it wholesale would
abandon the real-data-verification discipline that got Phases 1-7
actually built and working. Per explicit decision, only the pieces that
build on infrastructure that already exists are scoped here as Phase 9;
everything else from that vision stays an unscheduled idea (see below),
not a committed phase.

- **Knowledge graph**: migration 6's taxonomy schema (`TaxonomyTerms`
  with `ParentTermID` hierarchy, `BookTaxonomyTerms` many-to-many,
  `TaxonomyAliases`) already models exactly this shape of data - it's
  currently empty. Real relationship data (teacher/student, author/book,
  scholar/city) doesn't exist yet and needs its own extraction step
  (most realistically named-entity recognition over already-imported
  page text) before there's anything real to graph - this is a genuine
  R&D step, not just a UI, and should be scoped for real once attempted,
  not assumed to work.
- **Encyclopedia builder**: a natural extension of Phase 7's taxonomy
  GUI item, not new scope - once real taxonomy data exists (subjects,
  personalities, places, events), auto-assembling "every book/page
  linked to this term" into an encyclopedia-style page is a direct
  application of data that will already be there. Depends on Phase 7's
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

### Phase 10 — AI research assistant: **scheduled after Phase 9, not started**

Goes beyond search: a user asks a real comparative question ("how did
the four madhhabs differ on raising the hands in salah?") and the
assistant gathers real evidence across the corpus (via Phase 6/9's
semantic search and knowledge graph), quotes original passages with
real page references, and presents differing positions side by side.
**Hard requirement, not optional**: every claim must link back to a
real, openable page in a real book - no unsourced/unverifiable output.
Comparing scholarly positions is exactly the kind of feature flagged
earlier as carrying real accuracy risk in a religious-scholarship
domain - this phase's output is explicitly evidence-plus-citations, not
the assistant rendering its own verdict on which position is correct.

### Phase 11 — Translation engine: **scheduled after Phase 10, not started**

Real per-paragraph translation chain: original Arabic → Urdu → English,
plus word-by-word breakdown, grammar notes, and root-word analysis
(particularly valuable for Arabic morphology). A local translation
model is the realistic offline-first approach (consistent with every
other AI item in this roadmap); quality/accuracy needs a real check
before this is presented as authoritative, same caveat as Phase 10.

### Phase 12 — AI reading assistant: **scheduled after Phase 11, not started**

The in-reader interaction layer: highlight text while reading, then
ask the AI to explain, compare, translate (Phase 11), or summarize it,
and save the result as a note or bookmark (Phase 5's bookmark schema
already exists as a foundation). This phase is the UI/interaction
layer specifically - it calls into Phase 10 (research assistant) and
Phase 11 (translation) rather than re-implementing their logic, so
there's one real place each capability lives, not several.

### Phase 13 — Personal research workspace: **scheduled after Phase 12, not started**

Folders, collections, saved searches, saved AI conversations, and
export tools, built on top of Phase 5's existing bookmarks/recent-books
tables rather than replacing them. Real new scope: organizing
bookmarks/notes into named research projects and exporting a
collection (with real citations) as a document.

### Phase 14 — Educational features: **scheduled after Phase 13, not started**

Quizzes, flashcards, MCQs, spaced-repetition-style revision, lesson
plans, and a "teaching mode" view. Real dependency: question generation
needs to be grounded in real page content (same sourcing discipline as
Phase 10), not free-floating AI-generated trivia.

### Phase 15 — AI content generator: **scheduled after Phase 14, not started**

Produces structured output documents - lecture notes, khutbah outlines,
research-paper drafts, book reviews, comparison tables, citation lists
- from real evidence gathered the same way Phase 10 gathers it. This
phase is the "turn evidence into a formatted document" layer; it
depends on Phase 10 for the underlying evidence-gathering rather than
duplicating it.

### Phase 16 — Multimedia generation: **scheduled after Phase 15, not started**

Extends Phase 8's audio-overview stretch goal into a full multimedia
set: narrated podcasts, whiteboard-style animated explanations,
auto-generated slide decks, and timeline videos. Real AI-generated
*video* (as opposed to audio, already covered by Phase 8's TTS) is a
materially larger, separate engineering undertaking - each output
format in this phase needs its own feasibility check before being
committed to, not assumed to work at the same effort level as the rest.

### Phase 17 — Mobile companion app: **scheduled after Phase 16, not started**

The project's own stated goal already names this ("Windows desktop app
first, Android app later" - see Goal, above) - this phase is that
"later" spelled out for real: an offline mobile library, camera-based
OCR capture, and bookmark/download sync with the desktop app's
database. A materially different platform/tech stack from the current
PySide6 desktop app, not a small extension of it.

### Phase 18 — Developer APIs: **scheduled after Phase 17, not started**

Public APIs (search, translation, citation, book metadata, knowledge
graph, TTS) so other Islamic-research tools could build on this
platform's data. Real prerequisite: everything these APIs would expose
needs to already exist and be trustworthy (Phases 6-11) before it's
worth exposing to outside consumers.

### Phase 19 — Advanced research tools: **scheduled after Phase 18, not started**

The most research-grade, and most accuracy-sensitive, item set in this
roadmap - grouped together because they share one real requirement:
**scholarly review as a hard design constraint, not an afterthought**,
given this is Islamic scholarship, not general-purpose text analysis.
OCR confidence heatmaps, duplicate-edition detection, and variant-text
comparison between editions are comparatively low-risk (they're about
identifying differences, not asserting religious conclusions).
Citation-chain tracing, named-entity recognition, root-word/morphology
search, and automatic bibliography generation are real, buildable NLP
tasks with existing tooling to evaluate. **Isnad (chain-of-narration)
visualization and automatic literature-review generation are the
highest-risk items in this entire roadmap** - hadith authentication is
specialized scholarly work; an AI system that visualizes or summarizes
narrator chains without rigorous, expert-reviewed grounding risks
presenting unverified or wrong authentication judgments as fact. These
two sub-items specifically should not ship without real scholarly
review in the loop, not just a disclaimer.

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
