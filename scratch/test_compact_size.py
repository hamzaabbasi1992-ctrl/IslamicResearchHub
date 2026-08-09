import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    page_size = conn.execute("PRAGMA page_size;").fetchone()[0]
    total_pages = conn.execute("PRAGMA page_count;").fetchone()[0]
    freelist_pages = conn.execute("PRAGMA freelist_count;").fetchone()[0]

    active_pages = total_pages - freelist_pages
    active_bytes = active_pages * page_size
    active_gb = active_bytes / (1024 * 1024 * 1024)

    freelist_gb = (freelist_pages * page_size) / (1024 * 1024 * 1024)
    total_gb = (total_pages * page_size) / (1024 * 1024 * 1024)

print(f"Database Size Analysis:")
print(f"Current File Size on Disk: {total_gb:.2f} GB ({total_pages:,} pages)")
print(f"Freelist Unused Space:     {freelist_gb:.2f} GB ({freelist_pages:,} pages)")
print(f"Actual Active Data Size:   {active_gb:.2f} GB ({active_pages:,} pages)")
