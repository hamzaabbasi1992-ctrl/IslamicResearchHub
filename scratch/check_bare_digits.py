import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row

    # Purely digits titles (e.g. '26332', '33383')
    bare_digits = conn.execute(
        """
        SELECT b.BookID, b.Title, l.Name AS LibraryName,
               (SELECT Content FROM Pages p WHERE p.BookID = b.BookID ORDER BY PageNo LIMIT 1) AS Page1Text
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        WHERE b.Title GLOB '[0-9]*' AND b.Title NOT LIKE '% %' AND b.Title NOT LIKE '%-%'
        LIMIT 10
        """
    ).fetchall()

print(f"Sample Bare Digit Titles and their Page 1 Content:")
for b in bare_digits:
    p1 = (b['Page1Text'] or '').strip().replace('\n', ' ')[:100]
    print(f"  [BookID: {b['BookID']}] Title: '{b['Title']}' | Library: {b['LibraryName']}")
    print(f"    -> Page 1 Text: {p1}\n")
