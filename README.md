# IslamicResearchHub

IslamicResearchHub is a Python foundation for a future Islamic research platform.

Milestone 4 scans one folder recursively for Jibreel Mobile `.mjbz` files and
analyzes the in-memory books. It exports library reports without creating a
master database, search, OCR, AI, or PDF processing.

## Requirements

- Python 3.13
- SQLite (included with Python)

## Getting started

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
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
