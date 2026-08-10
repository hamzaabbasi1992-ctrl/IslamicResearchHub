"""Debug why search returns 0 results."""
import sqlite3
from pathlib import Path

p = Path("data/books.db")

# Test 1: plain connection
print("=== Test 1: plain sqlite3.connect ===")
conn_plain = sqlite3.connect(str(p))
conn_plain.row_factory = sqlite3.Row
fts_table = "Pages_fts"
query = "إحياء"
sql = (
    f"SELECT Books.BookID AS BookID, Books.Title AS Title, Pages.PageNo AS PageNo "
    f"FROM {fts_table} "
    f"JOIN Pages ON Pages.rowid = {fts_table}.rowid "
    f"JOIN Books ON Books.BookID = Pages.BookID "
    f"WHERE {fts_table} MATCH ? ORDER BY rank LIMIT 10"
)
rows = conn_plain.execute(sql, [query]).fetchall()
print(f"Plain connection results: {len(rows)}")
for r in rows[:3]:
    print(f"  BookID={r['BookID']} Page={r['PageNo']}")
conn_plain.close()

# Test 2: read-only URI connection
print("\n=== Test 2: read-only URI connection ===")
uri = f"{p.resolve().as_uri()}?mode=ro"
print(f"URI: {uri}")
conn_ro = sqlite3.connect(uri, uri=True)
conn_ro.row_factory = sqlite3.Row
rows_ro = conn_ro.execute(sql, [query]).fetchall()
print(f"Read-only URI results: {len(rows_ro)}")
for r in rows_ro[:3]:
    print(f"  BookID={r['BookID']} Page={r['PageNo']}")
conn_ro.close()

# Test 3: check which _index_exists detects
print("\n=== Test 3: index detection check ===")
conn2 = sqlite3.connect(str(p))
tables_check = {
    name: conn2.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None
    for name in ["PagesFTS", "PagesFTSNormalized", "Pages_fts"]
}
print("Table existence:", tables_check)
conn2.close()
