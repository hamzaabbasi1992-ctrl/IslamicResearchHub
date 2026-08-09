import sqlite3
from pathlib import Path

db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row

    # Total numeric titles count
    total_numeric = conn.execute(
        "SELECT COUNT(*) FROM Books WHERE Title GLOB '[0-9]*'"
    ).fetchone()[0]

    # Breakdown by Library
    by_library = conn.execute(
        """
        SELECT l.Name AS LibraryName, COUNT(*) AS Count
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        WHERE b.Title GLOB '[0-9]*'
        GROUP BY l.Name
        """
    ).fetchall()

    # Sample rows
    samples = conn.execute(
        """
        SELECT b.BookID, b.Title, b.Author, l.Name AS LibraryName, b.Category
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        WHERE b.Title GLOB '[0-9]*'
        LIMIT 15
        """
    ).fetchall()

print(f"Total Books with Numeric Titles: {total_numeric:,}")
print("\nBreakdown by Library:")
for row in by_library:
    print(f"  - {row['LibraryName']}: {row['Count']:,} books")

print("\nSample Numeric Books:")
for s in samples:
    print(f"  [ID: {s['BookID']}] Title: '{s['Title']}' | Library: {s['LibraryName']} | Category: {s['Category']}")
