import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row

    # Calculate text bytes per library
    rows = conn.execute(
        """
        SELECT l.Name AS LibraryName,
               COUNT(DISTINCT b.BookID) AS TotalBooks,
               SUM(COALESCE(b.PageCount, 0)) AS TotalPagesCount,
               COALESCE((
                   SELECT SUM(LENGTH(p.Content))
                   FROM Pages p
                   JOIN Books b2 ON b2.BookID = p.BookID
                   WHERE b2.LibraryID = l.LibraryID
               ), 0) AS TextBytes
        FROM Libraries l
        LEFT JOIN Books b ON b.LibraryID = l.LibraryID
        GROUP BY l.LibraryID, l.Name
        ORDER BY TextBytes DESC
        """
    ).fetchall()

    db_file_size_bytes = db_path.stat().st_size
    db_file_size_mb = db_file_size_bytes / (1024 * 1024)
    db_file_size_gb = db_file_size_bytes / (1024 * 1024 * 1024)

    total_text_bytes = sum(r["TextBytes"] for r in rows)

print(f"==========================================================================")
print(f"MASTER MAKTABA STORAGE SIZE BREAKDOWN REPORT")
print(f"==========================================================================")
print(f"Master Database File Size: {db_file_size_mb:,.1f} MB ({db_file_size_gb:.2f} GB)")
print(f"Total Text Character Bytes: {total_text_bytes / (1024 * 1024):,.1f} MB ({total_text_bytes / (1024 * 1024 * 1024):.2f} GB)")
print(f"==========================================================================\n")

print(f"{'Maktaba (Library) Name':<35} | {'Books':<8} | {'Pages':<12} | {'Raw Text Size':<15} | {'Est. DB Storage':<16} | {'Share (%)':<8}")
print("-" * 108)

for r in rows:
    lib_name = r["LibraryName"] or "Unknown"
    books_cnt = r["TotalBooks"]
    pages_cnt = r["TotalPagesCount"]
    text_b = r["TextBytes"]

    text_mb = text_b / (1024 * 1024)
    text_gb = text_b / (1024 * 1024 * 1024)
    text_str = f"{text_gb:.2f} GB" if text_gb >= 1 else f"{text_mb:.1f} MB"

    # Calculate proportional share of DB file size
    share_pct = (text_b / total_text_bytes * 100) if total_text_bytes > 0 else 0
    est_db_mb = (db_file_size_mb * (share_pct / 100)) if total_text_bytes > 0 else 0
    est_db_gb = est_db_mb / 1024
    est_db_str = f"{est_db_gb:.2f} GB" if est_db_gb >= 1 else f"{est_db_mb:.1f} MB"

    if books_cnt > 0 and pages_cnt == 0:
        text_str = "PDF Catalog"
        est_db_str = "< 1 MB"

    print(f"{lib_name:<35} | {books_cnt:<8,} | {pages_cnt:<12,} | {text_str:<15} | {est_db_str:<16} | {share_pct:<8.1f}%")
