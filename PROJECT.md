# Islamic Research Hub AI — Project Plan

Last updated: 2026-07-25 (kept in sync with `CHANGELOG.md`, which is the
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
- Shamela — excluded, explicit standing instruction.
- Calibre — not started, optional/low priority.

### Phase 2 — Master Database: **complete**

- Database verification tool, backup/restore tooling, versioned migration
  system (`PRAGMA user_version`, 5 real migrations applied to production).
- Authors normalized (650 authors, 4,466 books).
- Categories normalized into a cross-library taxonomy (691 categories,
  shared MJCN scheme across the two Jibreel libraries).
- Volumes modeled as a Series entity (412 series, 2,452 books).
- Footnotes — evaluated, no source data exists in any current library
  (checked the real `.mjbz` schema directly); not built.
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

### Phase 4 — Desktop GUI (PySide6): **not started**

Library, Search, Book Details, Viewer, Import Manager, Settings, Logs,
Duplicate Review tabs. The application/infrastructure layers this phase
needs (search, import, verification, backups) already exist and are
tested - this phase is primarily new `interfaces/` code plus a PySide6
composition root, not new business logic.

### Phase 5 — Book Viewer: **not started**

PDF, DjVu, EPUB rendering; jump-to-page; highlights; bookmarks; recent
books. Note: a browser-based viewer (PDF `#page=N` jump, in-app text
reading) already exists in the frozen web app - Phase 5 is about the
PySide6 desktop equivalent, not building page-jump from zero.

### Phase 6 — AI: **not started under phase discipline**

Semantic search, embeddings-based QA, citation engine, cross-book
comparison, research assistant. Note: a semantic search pilot
(sentence-transformers, hybrid RRF fusion with keyword search) already
exists, built before the phased roadmap was adopted and kept as-is per
explicit decision - it is not formally "Phase 6 work" and hasn't been
scaled to the full corpus.

## Items existing outside phase discipline (frozen, by explicit decision)

- **Local web app** (`web_app.py`, Flask): search, PDF page-jump, in-app
  reading. Built before the roadmap was adopted; kept working as-is; no
  further feature work until Phase 4 territory is reached, except direct
  bug fixes (e.g. the malformed-query crash fixed during Phase 3).
- **Semantic search pilot**: sentence-transformers + hybrid keyword/
  semantic fusion, built and validated on one subject (27 books) before
  the roadmap existed. Not scaled further until Phase 6.

## Not yet scheduled / future candidates

- **OCR**: now the single highest-value future item — most of the corpus
  (PDF Archive + Maknoon PDF collection + Jumma Bayanat, ~9,000 files) is
  metadata-only with no extracted text. Needs its own honest feasibility
  check (distinct from the native-text-extraction check already done for
  Phase 1) before any commitment.
- **Android app data recovery** (e.g. Maktaba Islam): investigate the
  app's on-device storage format before deciding whether/how to import.
- Duplicate candidate review (27 remaining Mobile/Desktop pairs).
- Performance index audit at the current, much larger corpus size.
