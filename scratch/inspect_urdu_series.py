import sqlite3
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

def is_urdu(text: str, lang: str) -> bool:
    if lang and lang.strip().lower() in ("ur", "urdu"):
        return True
    # Check for Urdu specific characters or words like جلد, نمبر, مفتی, رحمہ, مولانا
    if re.search(r"[\u067E\u0686\u0698\u06AF\u06BA\u06C1\u06D2]|جلد|نمبر|مفتی|مولانا|رحمہ", text):
        return True
    return False

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    books = conn.execute(
        """
        SELECT b.BookID, b.Title, b.Author, l.Name AS LibraryName, b.Language, b.VolumeNumber, b.SeriesID
        FROM Books b
        LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
        """
    ).fetchall()

urdu_books = [b for b in books if is_urdu(b["Title"], b["Language"])]

# Group by base title pattern (extracting volume numbers)
series_map = {}
for b in urdu_books:
    raw_title = b["Title"]
    # Match volume numbers like جلد 2, جلد نمبر 5, المجلد 3, Vol 4, or (2)
    v_match = re.search(r"(?:جلد|المجلد|نمبر|vol|volume)\s*(?:نمبر\s*)?(\d+)", raw_title, re.IGNORECASE)
    if not v_match:
        v_match = re.search(r"\((\d+)\)$", raw_title)
    if not v_match:
        v_match = re.search(r"\b(\d+)$", raw_title)

    vol_num = int(v_match.group(1)) if v_match else b["VolumeNumber"]

    # Base series title key
    base_title = re.sub(r"(?:جلد|المجلد|نمبر|vol|volume)\s*(?:نمبر\s*)?\d+", "", raw_title, flags=re.IGNORECASE)
    base_title = re.sub(r"\(\d+\)$", "", base_title)
    base_title = re.sub(r"\b\d+$", "", base_title)
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

multi_vol_series = {k: v for k, v in series_map.items() if len(v) > 1 or any(x["VolumeNumber"] is not None for x in v)}

print(f"Total Urdu Books Analyzed: {len(urdu_books):,}")
print(f"Total Urdu Multi-Volume Series Found: {len(multi_vol_series):,}\n")

print("Sample Urdu Multi-Volume Series:")
for base_title, item_list in list(multi_vol_series.items())[:15]:
    vols = [x["VolumeNumber"] for x in item_list if x["VolumeNumber"] is not None]
    vols_sorted = sorted(set(vols)) if vols else []
    max_v = max(vols_sorted) if vols_sorted else len(item_list)
    expected_vols = set(range(1, max_v + 1)) if vols_sorted else set(range(1, len(item_list) + 1))
    missing = sorted(expected_vols - set(vols_sorted)) if vols_sorted else []

    missing_str = ", ".join(str(m) for m in missing) if missing else "None (COMPLETE)"
    print(f"  📖 Series: '{base_title}' | Maktaba: {item_list[0]['Maktaba']}")
    print(f"     - Volumes Present: {len(item_list)} (Vols: {vols_sorted})")
    print(f"     - Missing / Remaining Volumes: {missing_str}\n")
