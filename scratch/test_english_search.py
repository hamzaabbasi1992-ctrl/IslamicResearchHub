import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

print("Testing Sub-Second English Full-Text Search in books.db...\n")

queries = ["prayer", "fasting", "patience", "Tawheed", "prophethood", "purification"]

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row

    # Verify English Islamic Library ID and Book Count
    lib_row = conn.execute("SELECT LibraryID FROM Libraries WHERE Name = 'English Islamic Library'").fetchone()
    lib_id = lib_row[0] if lib_row else None
    b_count = conn.execute("SELECT COUNT(*) FROM Books WHERE LibraryID = ?", (lib_id,)).fetchone()[0]

    print(f"Library Name: 'English Islamic Library' (LibraryID = {lib_id})")
    print(f"Ingested Books Count: {b_count} Books\n")

    for q in queries:
        t0 = time.time()
        results = conn.execute(
            """
            SELECT p.rowid AS PageID, b.Title AS BookTitle, b.Author, p.PageNo, p.Content
            FROM Pages_fts fts
            JOIN Pages p ON p.rowid = fts.rowid
            JOIN Books b ON b.BookID = p.BookID
            WHERE fts.Content MATCH ?
            LIMIT 5
            """,
            (q,)
        ).fetchall()
        t1 = time.time()
        elapsed = (t1 - t0) * 1000

        print(f"Query '{q}': {len(results)} matches found in {elapsed:.2f} ms")
        if results:
            print(f"   Top Match: [{results[0]['BookTitle']}] Page {results[0]['PageNo']}:")
            snippet = results[0]['Content'][:150].replace("\n", " ")
            print(f"   \"{snippet}...\"\n")
