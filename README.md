# IslamicResearchHub

IslamicResearchHub is a Python foundation for an Islamic research search
engine, intended to eventually power both Windows and Android applications.

The master database (`data/books.db`) is a multi-library corpus: every
imported book is tagged with a `LibraryID` so different sources stay
distinguishable, deduplicatable, and separately reportable, even though they
all share one full-text search index. Sources imported so far:

| Library | Source format | Books |
|---|---|---|
| Maktaba Jibreel (Mobile) | `.mjbz` (plain SQLite) | ~2,322 |
| Maktaba Jibreel (Desktop) | `.mjbx` (encrypted SQLite, same schema) | ~2,144 |
| Maktaba Al-Maknoon | Pre-extracted PDF text (OCR done upstream) | ~778 |
| Maktaba Jibreel (PDF Archive) | Raw PDFs, no text extraction | ~3,115 (metadata only) |
| Maktaba Al-Maknoon (PDF Archive) | Raw PDFs, no text extraction | ~3,258 (metadata only) |
| Jumma Bayanat | Raw PDFs (Friday sermons/general talks), no text extraction | ~2,718 (metadata only) |
| Maktaba Islam | `.mjbz` (same schema as Jibreel Mobile) | 48 |
| Maktaba Islam (PDF Archive) | Raw PDFs, no text extraction | 81 (metadata only) |

**Total: ~14,464 books.** OCR and full PDF text extraction are still out
of scope — the metadata-only libraries above are cataloged by title/path
only, not full text. Search also normalizes Arabic/Urdu spelling variants
(diacritics, letter forms) so e.g. "علی" and "علي" match each other - see
[PROJECT.md](PROJECT.md) for the full roadmap and current phase status.

## Requirements

- Python 3.11+
- SQLite (included with Python)
- Optional: `pip install -e .[ai]` for the semantic search pilot
  (sentence-transformers; large download, CPU-only unless you have a GPU)

## Getting started

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -e .[dev]  # adds pytest for running the test suite
```

Other optional extras: `.[web]` (the local web app), `.[ai]` (semantic
search pilot), `.[gui]` (the PySide6 desktop app), `.[build]` (packaging
it into an exe) — combine as needed, e.g. `pip install -e .[gui,build]`.

Double-click **`Open Islamic Research Hub.bat`** for the fastest way to
try the web app locally: it starts the server and opens your browser to
it automatically (`interfaces/web_app_cli.py` under the hood).

See [PROJECT.md](PROJECT.md) for the planned architecture and roadmap, and
[CHANGELOG.md](CHANGELOG.md) for a detailed history of what's been imported
and why.

## Scan a folder of verified MJBZ books

From the repository root, run:

```powershell
$env:PYTHONPATH = "src"
python -m islamic_research_hub path\\to\\book-folder --library "Library Name"
```

`--library` defaults to "Maktaba Jibreel (Mobile)" if omitted — always set it
explicitly when importing a source other than the original mobile library, or
books will be mistagged (ask me how I know).

The command scans `.mjbz` files recursively, shows progress, continues past
individual failures, and logs runtime messages to `logs/islamic_research_hub.log`.
Analysis is exported to `docs/library_report.json` and `docs/library_report.md`,
each book is written as a standalone Markdown file under
`library/<subject>/<title>.md`, and all scanned books are imported into the
master database at `data/books.db`, including a full-text search index over
every page.

## Import other sources

- **Maknoon** (pre-extracted PDF text): `python -m islamic_research_hub.interfaces.maknoon_import_cli <folder>`.
  Skips placeholder-only files (scanned PDFs Maknoon's own indexer could not OCR).
- **PDF collections with no extracted text**: `python -m islamic_research_hub.interfaces.pdf_metadata_import_cli <folder> --library "Name"`.
  Catalogs title + path only, no content, no search index entry.

Both reuse the same master database, library tagging, and dedup logic as the
main scan command.

## Search the library

Once `data/books.db` has been built by a scan, search it from the repository
root:

```powershell
$env:PYTHONPATH = "src"
python -m islamic_research_hub.interfaces.search_cli "your search terms"
```

Results are ranked by full-text relevance and include the book title, author,
library, page number, and a highlighted excerpt. Use `--database` to point at
a different database file, `--limit` to change how many results are returned
(default 20), and `--library "Name"`, `--author "Name"`, `--category "Name"`
to restrict results (omit any to search across everything). Boolean queries
(`AND`/`OR`/`NOT`), quoted phrases, and prefix (`term*`) queries are all
supported natively.

### Possible duplicates across libraries

Since libraries come from different, unrelated source systems, the same book
can end up cataloged more than once. Run the detector after importing new
sources:

```python
from pathlib import Path
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)
DuplicateCandidateRepository(Path("data/books.db")).detect_and_store()
```

This only *records* candidates (title-based, cross-library) into a
`DuplicateCandidates` table — it never deletes or merges anything
automatically. Query it directly to review:

```sql
SELECT b1.Title, l1.Name, b2.Title, l2.Name, dc.MatchType
FROM DuplicateCandidates dc
JOIN Books b1 ON b1.BookID = dc.BookID
JOIN Books b2 ON b2.BookID = dc.DuplicateOfBookID
JOIN Libraries l1 ON l1.LibraryID = b1.LibraryID
JOIN Libraries l2 ON l2.LibraryID = b2.LibraryID;
```

## Semantic search (pilot, not scaled to the full corpus)

A separate, experimental semantic (embedding-based) search path exists
alongside keyword search, piloted on one subject (~8,000 pages) rather than
the full ~900,000+ page corpus — see CHANGELOG.md for why. Requires
`pip install -e .[ai]` first.

```powershell
$env:PYTHONPATH = "src"
python -m islamic_research_hub.interfaces.semantic_index_cli "Root Category Name"
python -m islamic_research_hub.interfaces.semantic_search_cli "your search terms"
```

## Hybrid search (keyword + semantic, fused)

Combines keyword and semantic search into one ranked list via Reciprocal
Rank Fusion. Semantic search degrades gracefully — if the `ai` extra isn't
installed, or a page just isn't covered by the (pilot-scale) embedding
index, results simply come from keyword matching alone.

```powershell
$env:PYTHONPATH = "src"
python -m islamic_research_hub.interfaces.hybrid_search_cli "your search terms"
python -m islamic_research_hub.interfaces.hybrid_search_cli "your search terms" --keyword-only
```

Each result shows `matched by: keyword`, `matched by: semantic`, or
`matched by: keyword+semantic` (found by both, ranked higher) alongside its
fused score. Supports the same `--database`, `--limit`, and `--library`
flags as the other search commands.

## Desktop app (Phase 4, in progress)

A native Windows desktop app is being built with PySide6. Search is fully
working today; Viewer, Import, and Settings are visible but not built yet.

Run from source (`pip install -e .[gui]` first):

```powershell
python -m islamic_research_hub.interfaces.desktop_app
```

Build a standalone, portable `.exe` (`pip install -e .[gui,build]` first):

```powershell
.\build_installer.ps1
```

This produces `installation\IslamicResearchHub\IslamicResearchHub.exe` -
a self-contained folder that runs without a separate Python install. See
[installation/README.md](installation/README.md) (also available in
[Urdu](installation/README.ur.md) and [Arabic](installation/README.ar.md))
for how to run it, including where it expects `data\books.db`. The
`installation/` folder is a build output, not checked into git.
