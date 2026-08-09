import sqlite3
import re
from pathlib import Path

db_path = Path("data/books.db")

def normalize_title_key(title: str) -> str:
    t = str(title).strip().lower()
    t = re.sub(r"\s*\(\d+\)$", "", t)
    t = re.sub(r"\s*(جلد|المجلد|part|vol|volume)\s*\d+$", "", t)
    t = re.sub(r"[^\w\s\u0600-\u06FF]", "", t)
    return re.sub(r"\s+", " ", t).strip()

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row

    db_file_size_bytes = db_path.stat().st_size
    db_file_size_mb = db_file_size_bytes / (1024 * 1024)
    db_file_size_gb = db_file_size_bytes / (1024 * 1024 * 1024)

    total_books = conn.execute("SELECT COUNT(*) FROM Books").fetchone()[0]

    books = conn.execute("SELECT BookID, Title, COALESCE(PageCount, 0) AS PageCount FROM Books").fetchall()

    title_groups = {}
    for b in books:
        key = normalize_title_key(b["Title"])
        if key:
            title_groups.setdefault(key, []).append(b)

    redundant_books = 0
    redundant_pages = 0

    for key, b_list in title_groups.items():
        if len(b_list) > 1:
            # Sort by PageCount descending to keep best copy
            b_list.sort(key=lambda x: x["PageCount"], reverse=True)
            for r in b_list[1:]:
                redundant_books += 1
                redundant_pages += r["PageCount"]

    # Average page text size ~1.5 KB + index overhead ~1 KB = ~2.5 KB per page
    est_saved_bytes = redundant_pages * 2500
    est_saved_mb = est_saved_bytes / (1024 * 1024)
    est_saved_gb = est_saved_bytes / (1024 * 1024 * 1024)

print(f"Master Database File Size: {db_file_size_mb:.1f} MB ({db_file_size_gb:.2f} GB)")
print(f"Total Books: {total_books:,}")
print(f"Redundant Duplicate Books: {redundant_books:,}")
print(f"Redundant Pages to Remove: {redundant_pages:,}")
print(f"Estimated Space Savings: {est_saved_mb:.1f} MB ({est_saved_gb:.2f} GB)")
