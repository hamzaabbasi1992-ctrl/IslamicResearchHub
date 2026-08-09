import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row

    # Find books where Title is numeric only (or digits with extension/ID)
    numeric_books = conn.execute(
        """
        SELECT b.BookID, b.Title, l.Name AS LibraryName,
               (SELECT Content FROM Pages p WHERE p.BookID = b.BookID ORDER BY PageNo LIMIT 1) AS Page1Text
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        WHERE b.Title GLOB '[0-9]*' AND b.Title NOT LIKE '% %' AND b.Title NOT LIKE '%-%' AND b.Title NOT LIKE '%_%'
        LIMIT 30
        """
    ).fetchall()

print(f"Inspecting {len(numeric_books)} pure numeric books:")
for b in numeric_books:
    raw_text = (b["Page1Text"] or "").strip()
    first_line = raw_text.splitlines()[0].strip() if raw_text else "NO PAGE CONTENT"
    first_line_clean = first_line[:80]
    print(f"  [BookID: {b['BookID']}] Current Title: '{b['Title']}' | Maktaba: {b['LibraryName']}")
    print(f"    -> Extracted Page 1 Title Candidate: '{first_line_clean}'\n")
