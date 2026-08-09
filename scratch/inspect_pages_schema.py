import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    cols = conn.execute("PRAGMA table_info(Pages);").fetchall()
    print("Pages Table Columns:")
    for c in cols:
        print(f"  - {c['name']} ({c['type']})")
