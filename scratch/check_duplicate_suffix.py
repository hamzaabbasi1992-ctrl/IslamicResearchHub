import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row

    # Titles ending with (2), (3), or 2
    suffix_rows = conn.execute(
        """
        SELECT b.BookID, b.Title, l.Name AS LibraryName, b.Category
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        WHERE b.Title LIKE '% (2)' OR b.Title LIKE '%(2)' OR b.Title LIKE '% 2'
        """
    ).fetchall()

print(f"Total Books with (2) or 2 suffix: {len(suffix_rows):,}\n")
print("Sample Books with (2) suffix:")
for r in suffix_rows[:25]:
    print(f"  [ID: {r['BookID']}] Title: '{r['Title']}' | Maktaba: {r['LibraryName']}")
