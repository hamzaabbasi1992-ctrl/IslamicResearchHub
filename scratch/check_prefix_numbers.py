import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    prefix_rows = conn.execute(
        """
        SELECT b.BookID, b.Title, l.Name AS LibraryName, b.Category
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        WHERE b.Title GLOB '[0-9]_*' OR b.Title GLOB '[0-9][0-9]_*'
        LIMIT 25
        """
    ).fetchall()

    total_prefix = conn.execute(
        """
        SELECT COUNT(*) FROM Books
        WHERE Title GLOB '[0-9]_*' OR Title GLOB '[0-9][0-9]_*'
        """
    ).fetchone()[0]

print(f"Total Books starting with number prefix (e.g. 2_, 3_, 5_): {total_prefix:,}\n")
print("Sample Books:")
for r in prefix_rows:
    print(f"  [ID: {r['BookID']}] Title: '{r['Title']}' | Library: {r['LibraryName']}")
