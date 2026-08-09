import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT b.BookID, b.Title, l.Name AS LibraryName,
               (SELECT Content FROM Pages p WHERE p.BookID = b.BookID ORDER BY PageNo LIMIT 1) AS Page1Text
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        """
    ).fetchall()

numeric_books = []
for r in rows:
    title = str(r["Title"]).strip()
    # Check if title consists of digits or digits with extension like '1.pdf' or '26332'
    if title.isdigit() or ('.' in title and title.split('.')[0].isdigit()):
        numeric_books.append(r)

print(f"Total Books with Pure Numeric Titles: {len(numeric_books):,}\n")
for b in numeric_books[:25]:
    raw_text = (b["Page1Text"] or "").strip()
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    first_line = lines[0] if lines else "NO PAGE CONTENT"
    first_line_clean = first_line[:100]
    print(f"  [BookID: {b['BookID']}] Current Title: '{b['Title']}' | Maktaba: {b['LibraryName']}")
    print(f"    -> Extracted Page 1 Heading: '{first_line_clean}'\n")
