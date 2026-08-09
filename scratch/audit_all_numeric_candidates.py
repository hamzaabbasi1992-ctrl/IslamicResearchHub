import sqlite3
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

def needs_enrichment(title: str) -> bool:
    t = str(title).strip()
    if not t or t.lower() in ("untitled", "unknown", "none"):
        return True
    # Starts with a number or contains number codes
    if re.match(r"^\d+", t):
        return True
    if re.match(r"^book_\d+", t, re.IGNORECASE):
        return True
    if re.match(r"^doc_\d+", t, re.IGNORECASE):
        return True
    return False

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    books = conn.execute("SELECT BookID, Title FROM Books").fetchall()

candidates = [b for b in books if needs_enrichment(b["Title"])]

print(f"Total Books needing potential Title Enrichment: {len(candidates):,} / {len(books):,}")
for c in candidates[:30]:
    print(f"  [BookID: {c['BookID']}] Current Title: '{c['Title']}'")
