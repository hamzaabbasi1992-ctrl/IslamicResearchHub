import sqlite3
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    books = conn.execute(
        """
        SELECT b.BookID, b.Title, b.Author, l.Name AS LibraryName, b.Language, b.VolumeNumber
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        WHERE b.Title LIKE '%خطبات%'
           OR b.Title LIKE '%بیانات%'
           OR b.Title LIKE '%تقاریر%'
           OR b.Title LIKE '%تقریریں%'
           OR b.Title LIKE '%مواعظ%'
           OR b.Category LIKE '%Khutbat%'
           OR b.Category LIKE '%Bayanat%'
        """
    ).fetchall()

print(f"Total Urdu Khutbat & Bayanat Books Found in Library DB: {len(books):,}\n")

series_map = {}
for b in books:
    raw_title = b["Title"]
    # Extract volume number
    v_match = re.search(r"(?:جلد|المجلد|نمبر|vol|volume)\s*(?:نمبر\s*)?(\d+)", raw_title, re.IGNORECASE)
    if not v_match:
        v_match = re.search(r"\((\d+)\)$", raw_title)
    if not v_match:
        v_match = re.search(r"\b(\d+)$", raw_title)

    vol_num = int(v_match.group(1)) if v_match else b["VolumeNumber"]

    base_title = re.sub(r"(?:جلد|المجلد|نمبر|vol|volume)\s*(?:نمبر\s*)?\d+", "", raw_title, flags=re.IGNORECASE)
    base_title = re.sub(r"\(\d+\)$", "", base_title)
    base_title = re.sub(r"\b\d+$", "", base_title)
    base_title = base_title.replace("یونیکوڈ", "").replace("غیر موافق للمطبوع", "")
    base_title = re.sub(r"\s+", " ", base_title).strip(" -_")

    if not base_title:
        base_title = raw_title

    series_map.setdefault(base_title, []).append({
        "BookID": b["BookID"],
        "RawTitle": raw_title,
        "Author": b["Author"] or "Unknown",
        "Maktaba": b["LibraryName"] or "General",
        "VolumeNumber": vol_num,
    })

print(f"Unique Khutbat & Bayanat Series Found: {len(series_map):,}\n")
print("Top Khutbat & Bayanat Series in Library:")
for idx, (base_title, item_list) in enumerate(list(series_map.items())[:25], start=1):
    vols = [x["VolumeNumber"] for x in item_list if x["VolumeNumber"] is not None]
    vols_sorted = sorted(set(vols)) if vols else []
    print(f"  {idx}. '{base_title}' | Author: {item_list[0]['Author']}")
    print(f"     - Volumes Present: {len(item_list)} (Vols: {vols_sorted if vols_sorted else '1 Volume/Unnumbered'})\n")
