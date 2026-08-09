import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT l.Name AS LibraryName,
               COUNT(b.BookID) AS TotalBooks,
               SUM(CASE WHEN b.PageCount > 0 THEN 1 ELSE 0 END) AS TextBooksCount,
               SUM(CASE WHEN b.PageCount = 0 OR b.PageCount IS NULL THEN 1 ELSE 0 END) AS PDFArchiveBooksCount,
               SUM(COALESCE(b.PageCount, 0)) AS TotalPagesCount
        FROM Libraries l
        LEFT JOIN Books b ON b.LibraryID = l.LibraryID
        GROUP BY l.LibraryID, l.Name
        ORDER BY TotalBooks DESC
        """
    ).fetchall()

    total_books_sum = conn.execute("SELECT COUNT(*) FROM Books").fetchone()[0]
    total_pages_sum = conn.execute("SELECT SUM(COALESCE(PageCount, 0)) FROM Books").fetchone()[0]
    total_text_sum = conn.execute("SELECT COUNT(*) FROM Books WHERE PageCount > 0").fetchone()[0]
    total_pdf_sum = conn.execute("SELECT COUNT(*) FROM Books WHERE PageCount IS NULL OR PageCount = 0").fetchone()[0]

print(f"==========================================================================")
print(f"MASTER LIBRARY INVENTORY & STATISTICAL BREAKDOWN REPORT")
print(f"==========================================================================")
print(f"Total Master Books:    {total_books_sum:,}")
print(f"Searchable Text Books: {total_text_sum:,}")
print(f"PDF / Audio Archives:  {total_pdf_sum:,}")
print(f"Total Master Pages:    {total_pages_sum:,}")
print(f"==========================================================================\n")

print(f"{'Maktaba (Library)':<35} | {'Type':<15} | {'Total Books':<12} | {'Text Books':<12} | {'PDF/Audio':<10} | {'Total Pages':<14}")
print("-" * 110)

for r in rows:
    lib_name = r["LibraryName"] or "Unknown"
    is_pdf = "PDF" in lib_name or "Bayanat" in lib_name
    fmt_type = "Scanned PDF / Audio" if is_pdf else "Searchable Text"

    print(f"{lib_name:<35} | {fmt_type:<15} | {r['TotalBooks']:<12,} | {r['TextBooksCount']:<12,} | {r['PDFArchiveBooksCount']:<10,} | {r['TotalPagesCount']:<14,}")
