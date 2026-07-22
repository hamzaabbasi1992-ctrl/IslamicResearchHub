# Project Review — IslamicResearchHub

Review date: 2026-07-22
Scope: full repository read (docs, source, tests, logs, config). No code was modified.

## 1. Current Project Status

- Only three project documents exist: [README.md](README.md), [PROJECT.md](PROJECT.md), and [claude.md](claude.md). `DESIGN.md`, `ROADMAP.md`, `TODO.md`, and `CHANGELOG.md` do not exist in the repository.
- Per [PROJECT.md](PROJECT.md)'s seven-milestone roadmap (Foundation → Domain design → Persistence → Application workflows → Interfaces → Document ingestion → AI integration), the code has already moved past what the docs describe as "in scope." The single CLI command now performs folder scanning, in-memory extraction, library analysis/report export, **and** master-database persistence in one run — i.e. milestones 1–4 are functionally done and milestone 5 (Interfaces) is minimally started (one CLI entry point, no web/API).
- [README.md](README.md) is out of date: it states the scan "exports library reports without creating a master database," but [cli.py](src/islamic_research_hub/interfaces/cli.py) now builds `data/books.db` via `MasterDatabaseBuilder` as its final step. This is documentation drift, not a code problem.
- A real run has already happened against production-like data: `data/books.db` is **3.1 GB** on disk, and `logs/islamic_research_hub.log` shows a successful scan/extraction of a real `.mjbz` file (`35.mjbz`, 316 pages, 409 TOC entries) as recently as 2026-07-22.

## 2. What Has Already Been Completed

**Domain layer** (`domain/models`) — framework-free, immutable, typed:
- `Book`, `Category`, `Chapter`, `Page` (frozen, slotted dataclasses) in [book.py](src/islamic_research_hub/domain/models/book.py)
- `TableSchema` in [database_schema.py](src/islamic_research_hub/domain/models/database_schema.py)
- `LibraryReport`, `BookSize`, `DuplicateMetadataValue` (+ `to_dict()` for serialization) in [library_report.py](src/islamic_research_hub/domain/models/library_report.py)

**Application layer** (`application/`) — orchestration behind `Protocol` ports:
- `MjbzInspectionService` — validates and inspects one `.mjbz` file's schema
- `MjbzBookExtractionService` — validates the four required tables/columns, then extracts
- `MjbzFolderScanner` — recursive scan, continues past per-file failures, reports progress
- `LibraryAnalyzer` — metadata/content quality stats, duplicates, largest/smallest book
- `MasterDatabaseBuilder` — coordinates import of a scan result into the master DB

**Infrastructure layer** (`infrastructure/`) — concrete adapters:
- `SqliteMjbzInspector`, `SqliteMjbzBookReader` — both open source `.mjbz` files **read-only** (`?mode=ro`), preventing accidental mutation of source data
- `MasterBookRepository` — creates/populates `data/books.db` (`Books`, `Categories`, `Chapters`, `Pages` tables), skips already-imported sources by `Source` path, per-book transactions
- `LibraryReportExporter` — writes `docs/library_report.json` and `docs/library_report.md`

**Interfaces** — single `cli.py` composition root wiring all of the above; UTF-8-safe stdout for Arabic/Persian text; terminal progress bar.

**Shared** — `logging_config.py` sets up console + rotating-free file logging to `logs/islamic_research_hub.log`, idempotent (`if root_logger.handlers: return`).

**Tests** (`tests/`, 5 files) — one file per major component: inspection, book reader (full verified-schema extraction incl. category/TOC tree building), folder scanner (recursion, non-`.mjbz` filtering, failure continuation), library analyzer (metadata/content quality, duplicates), master repository (import + skip-on-repeat, row content).

## 3. Architecture Review

The implementation follows [PROJECT.md](PROJECT.md)'s intended layering well:

- **Dependency direction is correct**: domain has zero imports from application/infrastructure; application depends only on domain + its own `Protocol` contracts; infrastructure implements those Protocols; `cli.py` is the only place concrete adapters are wired to services (a proper composition root).
- **Ports/adapters (dependency inversion)** is used consistently — e.g. `BookExtractor`, `BookReader`, `SchemaInspector`, `MasterDatabaseWriter` are all `Protocol` classes the application layer depends on, with infrastructure classes satisfying them structurally (no inheritance coupling). This is exactly what supports the "later replacement of adapters" goal stated in PROJECT.md.
- **Zero third-party dependencies** (`dependencies = []` in [pyproject.toml](pyproject.toml)) — everything is stdlib (`sqlite3`, `pathlib`, `argparse`, `logging`, `dataclasses`). Keeps the foundation lean, consistent with the "repository scaffolding" scope.

Two structural inconsistencies worth noting (not defects, just drift from the stated plan):

1. `domain/repositories/` exists as an empty placeholder package. PROJECT.md assigns "repository contracts" to the domain layer, but the actual repository/reader/inspector contracts (`BookExtractor`, `MasterDatabaseWriter`, etc.) are defined as `Protocol`s inside `application/*.py` instead. The pattern works, but the empty package is currently dead weight and may confuse future contributors about where contracts belong.
2. `config/` is also an empty placeholder. Nothing in the CLI is currently configurable — output paths (`docs/`, `data/books.db`, `logs/`) are hardcoded in `cli.py` and `MasterDatabaseBuilder`'s default argument, even though PROJECT.md describes `config` as owning "configuration contracts and settings integration."

## 4. Code Quality Review

Overall quality is high and consistent:

- Every public class/function has a docstring; all signatures use modern type hints (`X | None`, `tuple[T, ...]`, frozen `slots=True` dataclasses).
- SQL identifiers from trusted sources (SQLite's own `sqlite_master` catalog) are manually quoted/escaped rather than string-concatenated blindly, with a docstring noting the trust boundary; all row **values** go through parameterized queries — no injection risk found.
- Recursive tree-building (`_build_tree` in `mjbz_book_reader.py`) explicitly handles orphaned nodes and cyclic parent references (via an `ancestors` frozenset guard) rather than assuming clean input — good defensive handling of real-world/malformed data.
- Read-only DB connections are used everywhere a source `.mjbz` file is opened, which is a correct and deliberate safety property given these are user-supplied source files.
- Tests use real SQLite databases in `tmp_path` rather than mocks (consistent with a preference for integration-style tests over mocking), plus a hand-written `FakeExtractor` Protocol-fake for the scanner test — appropriately lightweight.
- Logging vs. user-facing output is intentionally split: `LOGGER.info/.warning/.exception` for the diagnostic trail, `print()` for CLI summaries — a reasonable and consistent convention throughout.

Minor duplication (small, but flagged per the project's "never duplicate code" rule):
- An identical recursive `_count_chapters(chapters)` helper is independently defined in three places: [mjbz_folder_scanner.py](src/islamic_research_hub/application/mjbz_folder_scanner.py), [library_analyzer.py](src/islamic_research_hub/application/library_analyzer.py), and [master_book_repository.py](src/islamic_research_hub/infrastructure/persistence/master_book_repository.py).
- Tree-flattening helpers (`_flatten_chapters`, `_flatten_categories`) are duplicated between `library_analyzer.py` and `master_book_repository.py`.

These are 3–5 line pure functions, so the duplication cost is low today, but a shared `shared/tree_utils.py` (or similar) would remove it cleanly if this pattern grows further.

## 5. Possible Technical Debt

- **No test coverage for the two riskiest integration points**: `MasterDatabaseBuilder` (`application/master_database_builder.py`) and `interfaces/cli.py` itself have no tests. Every other application/infrastructure class has a corresponding test file; these two — which wire everything together — do not.
- **Python version mismatch**: [pyproject.toml](pyproject.toml) declares `requires-python = ">=3.13"`, but the only interpreter available in this environment is Python 3.11.9, and `pytest` is not installed at all — the test suite could not be executed during this review. It's unclear whether 3.13 is actually required by any language feature in use (nothing observed requires it) or if the constraint is aspirational.
- **No pinned dev dependencies**: [requirements.txt](requirements.txt) is a stub comment with no packages, including no `pytest`. There's currently no reproducible way to `pip install` what's needed to run the test suite or any linter/type-checker implied by the `.gitignore` entries (`.mypy_cache/`, `.ruff_cache/`).
- **No CI configuration** (no `.github/workflows/`, no `tox`/`nox` setup) — nothing currently enforces tests/lint/type-checks automatically.
- **Hardcoded paths**: `docs/`, `data/books.db`, `logs/` are hardcoded rather than sourced from the (currently empty) `config` package, so there's no way to point the tool at a different output location without editing code.

## 6. Risks

- **`data/books.db` is 3.1 GB and growing** with each scan, with no documented retention, backup, or rebuild policy. It's correctly `.gitignore`d, so no repo-bloat risk, but there is an operational/disk-usage risk as more libraries are scanned.
- **No indexes or foreign keys on the master schema** (`Categories`, `Chapters`, `Pages` all reference `BookID` with no `FOREIGN KEY` constraint and no index). At multi-GB scale this will make any future per-book lookup or join slow; currently the app only ever inserts, so it hasn't surfaced yet.
- **Broad exception handling in the folder scanner**: `mjbz_folder_scanner.py` catches bare `except Exception` per file so one bad file doesn't stop the whole scan (intentional, and logged via `LOGGER.exception`) — but this also silently absorbs *programming* errors (e.g., a bug inside the reader) as if they were bad input files. Worth confirming this breadth is deliberate rather than a convenient catch-all.
- **No automated quality gate**: without CI, a regression in any of the untested paths (`MasterDatabaseBuilder`, `cli.py`) could ship unnoticed.

## 7. Recommended Next Milestone

Given the roadmap in PROJECT.md and the gaps above, the highest-value next milestone is **hardening what already exists** before starting Milestone 6 (Document ingestion) or 7 (AI integration), which will add significantly more load on top of this foundation:

1. **Close the test gap** — add tests for `MasterDatabaseBuilder` and an end-to-end `cli.main()` test (using `tmp_path` and a fake/real small `.mjbz` fixture), matching the coverage pattern already established for every other component.
2. **Fix environment reproducibility** — reconcile the `requires-python` constraint with the actually-available interpreter, and pin `pytest` (plus any intended lint/type-check tools) in a dev-dependency group so `pytest` is runnable at all.
3. **Refresh README.md** to reflect that a master database is now built (currently describes older, pre-persistence behavior).
4. **Populate or remove the empty `config`/`domain/repositories` placeholders** — either give `config` real settings contracts (starting with the hardcoded output paths) and move the application-layer `Protocol`s into `domain/repositories`, or document that the current locations are intentional so the placeholders stop looking unfinished.

These are foundation-strengthening steps rather than new features, consistent with "extend the existing architecture, not redesign it." No code was changed as part of this review.
