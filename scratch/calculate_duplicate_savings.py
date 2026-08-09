import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row

    db_file_size_bytes = db_path.stat().st_size
    db_file_size_mb = db_file_size_bytes / (1024 * 1024)
    db_file_size_gb = db_file_size_bytes / (1024 * 1024 * 1024)

    total_books = conn.execute("SELECT COUNT(*) FROM Books").fetchone()[0]
    total_pages = conn.execute("SELECT COUNT(*) FROM Pages").fetchone()[0]

    # Calculate duplicate pages and text size
    # Exact duplicate titles (excluding volume indicators)
    rows = conn.execute(
        """
        SELECT b.BookID, b.Title, b.PageCount,
               COALESCE((SELECT SUM(LENGTH(Content)) FROM Pages p WHERE p.BookID = b.BookID), 0) AS TextBytes
        FROM Books b
        """
    ).fetchall()

    title_groups = {}
    for r in rows:
        title = r["Title"].strip().lower()
        title_groups.setdefault(title, []).append(r)

    redundant_books_count = 0
    redundant_text_bytes = 0
    redundant_pages_count = 0

    for title, b_list in title_groups.items():
        if len(b_list) > 1:
            # Sort by text bytes descending so we keep the largest/best copy as primary
            b_list.sort(key=lambda x: x["TextBytes"], reverse=True)
            # All copies after the first are redundant
            for redundant in b_list[1:]:
                redundant_books_count += 1
                redundant_text_bytes += redundant["TextBytes"]
                redundant_pages_count += redundant["PageCount"]

    redundant_text_mb = redundant_text_bytes / (1024 * 1024)

print(f"Current Master Database Size: {db_file_size_mb:.1f} MB ({db_file_size_gb:.2f} GB)")
print(f"Total Books: {total_books:,}")
print(f"Total Pages: {total_pages:,}\n")

print(f"Redundant Duplicate Books: {redundant_books_count:,}")
print(f"Redundant Text Pages: {redundant_pages_count:,}")
print(f"Estimated Raw Text Space Savings: {redundant_text_mb:.1f} MB")
print(f"Estimated Total SQLite DB Reduction (including indexes): {redundant_text_mb * 1.8:.1f} MB (~{(redundant_text_mb * 1.8) / 1024:.2f} GB)")
