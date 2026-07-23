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

OCR and full PDF text extraction are still out of scope — the PDF Archive
library above is cataloged by title/path only, not full text.

## Requirements

- Python 3.11+
- SQLite (included with Python)
- Optional: `pip install -e .[ai]` for the semantic search pilot
  (sentence-transformers; large download, CPU-only unless you have a GPU)

## Getting started

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .[dev]  # adds pytest for running the test suite
```

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
page number, and a highlighted excerpt. Use `--database` to point at a
different database file and `--limit` to change how many results are
returned (default 20).

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
