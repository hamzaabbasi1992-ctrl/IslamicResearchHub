"""
Debug: check if PagesFTS (content-backed FTS) is populated or empty.
"""
import sqlite3

conn = sqlite3.connect("data/books.db")

# Check Pages_fts - this is what currently works
pages_fts_count = conn.execute("SELECT COUNT(*) FROM Pages_fts").fetchone()[0]
print(f"Pages_fts row count: {pages_fts_count}")

# Check PagesFTS - content-backed FTS pointing to Pages via PageID
# Content-backed FTS does not store data itself; it queries the 'content' table
# But we can test a simple search through it
try:
    rows = conn.execute(
        "SELECT rowid FROM PagesFTS WHERE PagesFTS MATCH ? LIMIT 5",
        ["إحياء"]
    ).fetchall()
    print(f"PagesFTS search hits: {len(rows)}")
except Exception as e:
    print(f"PagesFTS search error: {e}")

# Check what rowid PagesFTS uses
print("\nPagesFTS SQL:")
print(conn.execute("SELECT sql FROM sqlite_master WHERE name='PagesFTS'").fetchone()[0])

print("\nPages_fts SQL:")
print(conn.execute("SELECT sql FROM sqlite_master WHERE name='Pages_fts'").fetchone()[0])

print("\nPages table schema:")
print(conn.execute("SELECT sql FROM sqlite_master WHERE name='Pages'").fetchone()[0])
