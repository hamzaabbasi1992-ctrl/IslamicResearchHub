"""Ultra-fast CLI & Utility to extract real titles from Page 1 content for numeric or unlabelled books.

Finds books whose Title is numeric (e.g. '0', '26332', '33383') or starts with numeric prefixes ('01-', '14_'),
inspects Page 1 for the main heading/title line, and updates Books.Title in database.
"""

import argparse
import logging
import re
import sqlite3
from contextlib import closing
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")


def is_numeric_or_prefixed(title: str) -> bool:
    """Check if title is numeric, generic, or starts with a numeric prefix."""
    t = str(title).strip()
    if not t or t.lower() in ("untitled", "unknown", "none"):
        return True
    if t.isdigit():
        return True
    if re.match(r"^\d+[\s\-_.]", t):
        return True
    if re.match(r"^(book|doc|pdf)_\d+", t, re.IGNORECASE):
        return True
    if t.replace("_", "").replace("-", "").isdigit():
        return True
    return False


def extract_title_from_text(page_content: str) -> str | None:
    """Extract first non-empty meaningful heading line from page text."""
    if not page_content:
        return None
    lines = [line.strip() for line in page_content.splitlines() if line.strip()]
    for line in lines[:5]:
        line_clean = re.sub(r"\s+", " ", line).strip()
        if len(line_clean) >= 4 and not line_clean.isdigit() and not re.match(r"^\d+\s*$", line_clean):
            return line_clean[:120].strip()
    return None


def clean_existing_title(raw_title: str) -> str:
    """Clean underscores and hyphens in existing prefixed titles."""
    match = re.match(r"^(\d+[\s\-_.]*)(.*)", raw_title)
    if match:
        num_prefix = match.group(1).strip().rstrip("-_.")
        rest = match.group(2).strip().replace("_", " ").replace("-", " ")
        rest_clean = re.sub(r"\s+", " ", rest).strip()
        if num_prefix and rest_clean:
            return f"{num_prefix} - {rest_clean}"
        elif rest_clean:
            return rest_clean
    return raw_title.replace("_", " ").strip()


def enrich_numeric_book_titles(database_path: Path = DEFAULT_DATABASE_PATH) -> tuple[int, int]:
    """Enrich numeric book titles ultra-fast via single JOIN query."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    enriched_count = 0
    total_candidates = 0

    with closing(sqlite3.connect(database_path)) as conn:
        conn.row_factory = sqlite3.Row

        # Fast JOIN query on Page 1
        rows = conn.execute(
            """
            SELECT b.BookID, b.Title, p.Content
            FROM Books b
            LEFT JOIN Pages p ON p.BookID = b.BookID AND p.PageNo = 1
            """
        ).fetchall()

        updates = []

        for row in rows:
            book_id = row["BookID"]
            raw_title = str(row["Title"]).strip()

            if is_numeric_or_prefixed(raw_title):
                total_candidates += 1
                is_pure_digits = raw_title.isdigit() or raw_title.replace("_", "").replace("-", "").isdigit()
                page_heading = extract_title_from_text(row["Content"])

                if is_pure_digits:
                    if page_heading:
                        new_title = f"{raw_title} - {page_heading}"
                    else:
                        new_title = raw_title
                else:
                    cleaned = clean_existing_title(raw_title)
                    if page_heading and len(page_heading) > len(cleaned):
                        prefix_match = re.match(r"^(\d+)", raw_title)
                        prefix_str = prefix_match.group(1) if prefix_match else ""
                        new_title = f"{prefix_str} - {page_heading}" if prefix_str else page_heading
                    else:
                        new_title = cleaned

                if new_title != raw_title:
                    updates.append((new_title, book_id))
                    enriched_count += 1

        if updates:
            conn.executemany("UPDATE Books SET Title = ? WHERE BookID = ?", updates)
            conn.commit()

    return enriched_count, total_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich all numeric book titles from Page 1 text")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    args = parser.parse_args()

    enriched, total = enrich_numeric_book_titles(args.database)
    print(f"Comprehensive Title Enrichment Complete:")
    print(f"Total Numeric / Prefixed Books Inspected: {total:,}")
    print(f"Books Enriched & Cleaned: {enriched:,}")


if __name__ == "__main__":
    main()
