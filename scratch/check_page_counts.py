import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row

    # Total books with PageCount = 0 or NULL
    zero_pagecount = conn.execute(
        "SELECT COUNT(*) FROM Books WHERE PageCount IS NULL OR PageCount = 0"
    ).fetchone()[0]

    # Of those zero PageCount books, how many actually HAVE pages in Pages table?
    has_pages_in_table = conn.execute(
        """
        SELECT COUNT(DISTINCT b.BookID)
        FROM Books b
        JOIN Pages p ON p.BookID = b.BookID
        WHERE b.PageCount IS NULL OR b.PageCount = 0
        """
    ).fetchone()[0]

    # Breakdown by Library
    by_library = conn.execute(
        """
        SELECT l.Name AS LibraryName, COUNT(*) AS TotalZero,
               COUNT(p.BookID) AS HasPages
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        LEFT JOIN (SELECT DISTINCT BookID FROM Pages) p ON p.BookID = b.BookID
        WHERE b.PageCount IS NULL OR b.PageCount = 0
        GROUP BY l.Name
        """
    ).fetchall()

    total_books = conn.execute("SELECT COUNT(*) FROM Books").fetchone()[0]

print(f"Total Books in Master Database: {total_books:,}")
print(f"Total Books with PageCount = 0 or N/A: {zero_pagecount:,}")
print(f"  -> Books with PageCount=0 that ACTUALLY HAVE pages in Pages table: {has_pages_in_table:,}")
print(f"  -> Metadata-Only / PDF-only books without text pages: {zero_pagecount - has_pages_in_table:,}\n")

print("Breakdown by Library:")
for r in by_library:
    print(f"  - {r['LibraryName']}: {r['TotalZero']:,} books with PageCount=0 ({r['HasPages']:,} have text pages)")
