# IslamicResearchHub

IslamicResearchHub is a Python foundation for an Islamic research search
engine, intended to eventually power both Windows and Android applications.

The current tooling scans one folder recursively for Jibreel Mobile `.mjbz`
files, analyzes the in-memory books, exports library reports and per-book
Markdown files, and imports everything into a master SQLite database with a
full-text search index. OCR, AI, and PDF processing are still out of scope.

## Requirements

- Python 3.11+
- SQLite (included with Python)

## Getting started

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .[dev]  # adds pytest for running the test suite
```

See [PROJECT.md](PROJECT.md) for the planned architecture and roadmap.

## Scan a folder of verified MJBZ books

From the repository root, run:

```powershell
$env:PYTHONPATH = "src"
python -m islamic_research_hub path\\to\\book-folder
```

The command scans `.mjbz` files recursively, shows progress, continues past
individual failures, and logs runtime messages to `logs/islamic_research_hub.log`.
Analysis is exported to `docs/library_report.json` and `docs/library_report.md`,
each book is written as a standalone Markdown file under
`library/<subject>/<title>.md`, and all scanned books are imported into the
master database at `data/books.db`, including a full-text search index over
every page.

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
