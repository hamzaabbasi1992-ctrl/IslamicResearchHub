import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    # Check page count and freelist count
    page_size = conn.execute("PRAGMA page_size;").fetchone()[0]
    page_count = conn.execute("PRAGMA page_count;").fetchone()[0]
    freelist_count = conn.execute("PRAGMA freelist_count;").fetchone()[0]

    freelist_bytes = freelist_count * page_size
    freelist_gb = freelist_bytes / (1024 * 1024 * 1024)
    total_gb = (page_count * page_size) / (1024 * 1024 * 1024)

print(f"Total Database Pages: {page_count:,} ({total_gb:.2f} GB)")
print(f"Freelist Unused Pages: {freelist_count:,} ({freelist_gb:.2f} GB)")
print(f"Page Size: {page_size} bytes")
