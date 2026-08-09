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

    books = conn.execute(
        """
        SELECT b.BookID, b.Title, l.Name AS LibraryName
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        """
    ).fetchall()

    title_groups = {}
    for b in books:
        key = normalize_title_key(b["Title"])
        if key:
            title_groups.setdefault(key, []).append(b)

    same_maktaba_groups = 0
    same_maktaba_books = 0

    different_maktaba_groups = 0
    different_maktaba_books = 0

    library_pair_counts = {}

    for key, b_list in title_groups.items():
        if len(b_list) > 1:
            libraries = {b["LibraryName"] for b in b_list}
            if len(libraries) == 1:
                same_maktaba_groups += 1
                same_maktaba_books += len(b_list)
            else:
                different_maktaba_groups += 1
                different_maktaba_books += len(b_list)

                # Record pair combination
                lib_tuple = tuple(sorted(list(libraries)))
                library_pair_counts[lib_tuple] = library_pair_counts.get(lib_tuple, 0) + 1

print(f"Duplicate Groups Breakdown:\n")
print(f"1. Duplicates WITHIN THE SAME Maktaba:")
print(f"   - Groups: {same_maktaba_groups:,}")
print(f"   - Total Books: {same_maktaba_books:,}\n")

print(f"2. Duplicates ACROSS DIFFERENT Maktabas:")
print(f"   - Groups: {different_maktaba_groups:,}")
print(f"   - Total Books: {different_maktaba_books:,}\n")

print("Top Library Pairs Sharing Duplicates:")
for libs, count in sorted(library_pair_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"   - {' <-> '.join(libs)}: {count:,} shared books")
