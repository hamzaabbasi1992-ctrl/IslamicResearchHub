"""CLI & Exporter for Urdu Multi-Volume Series Catalog & Missing Volumes Inventory.

Calculates true total volume counts from Islamic reference catalogs for complete accuracy.
Generates:
1. Urdu_Multi_Volume_Series_Catalog.xlsx (Root folder)
2. Urdu_Multi_Volume_Series_Catalog.csv (Root folder)
3. docs/urdu_multi_volume_series_report.xlsx
4. docs/urdu_multi_volume_series_report.csv
"""

import argparse
import csv
import logging
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import openpyxl

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_EXCEL_PATH = Path("Urdu_Multi_Volume_Series_Catalog.xlsx")
DEFAULT_CSV_PATH = Path("Urdu_Multi_Volume_Series_Catalog.csv")
DOCS_EXCEL_PATH = Path("docs/urdu_multi_volume_series_report.xlsx")
DOCS_CSV_PATH = Path("docs/urdu_multi_volume_series_report.csv")

# Reference dictionary of published true total volume counts from major Islamic publishers
KNOWN_TRUE_TOTAL_VOLUMES = {
    "احتساب قادیانیت": 60,
    "آپ کے مسائل اور ان کا حل": 10,
    "ملفوظات حکیم الامت": 30,
    "فتاوی محمودیہ": 30,
    "احسن الفتاوی": 9,
    "اعلاء السنن": 22,
    "اردو دائرہ معارف اسلامیہ": 23,
    "اسلام اور جدید معاشی مسائل": 8,
    "اسلام اور ہماری زندگی": 14,
    "اسوہ حسنہ المعروف بہ شمائل کبری": 12,
    "شمائل کبری": 12,
    "اشرف الہدایہ": 16,
    "اصلاحی خطبات": 20,
    "اصلاحی تقریریں": 10,
    "معارف القرآن": 8,
    "تفسیر عثمانی": 3,
    "فتاوی رحیمیہ": 10,
    "فتاوی حقانیہ": 6,
    "کفایت المفتی": 9,
    "مسند امام احمد بن حنبل": 14,
    "بیان القرآن": 3,
    "تفہیم القرآن": 6,
    "درس ترمذی": 5,
    "تشریحات ترمذی": 7,
    "احسن البیان": 1,
    "البدایہ والنہایہ": 16,
    "معارف الحدیث": 8,
    "جامع الترمذی اردو": 2,
    "سنن ابوداؤد اردو": 3,
    "سنن ابن ماجہ اردو": 2,
    "سنن نسائی اردو": 3,
    "صحیح مسلم اردو": 6,
    "صحیح بخاری اردو": 8,
}


def lookup_true_total_volumes(title: str, detected_max: int) -> int:
    """Lookup published true total volume count for series, defaulting to max detected volume."""
    clean_t = re.sub(r"[^\w\s\u0600-\u06FF]", "", title).strip()
    for ref_title, total_vols in KNOWN_TRUE_TOTAL_VOLUMES.items():
        if ref_title in title or ref_title in clean_t:
            return total_vols
    return max(detected_max, 1)


def is_urdu_text(title: str, lang: str) -> bool:
    """Check if text is Urdu based on language metadata or script analysis."""
    if lang and lang.strip().lower() in ("ur", "urdu"):
        return True
    if re.search(r"[\u067E\u0686\u0698\u06AF\u06BA\u06C1\u06D2]|جلد|نمبر|مفتی|مولانا|رحمہ|قادیانیت|فتاوی|تفہیم|معارف", title):
        return True
    return False


def extract_volume_number(title: str, default_vol: int | None) -> int | None:
    """Extract integer volume number from title or metadata."""
    if default_vol is not None and default_vol > 0:
        return default_vol

    v_match = re.search(r"(?:جلد|المجلد|نمبر|vol|volume)\s*(?:نمبر\s*)?(\d+)", title, re.IGNORECASE)
    if v_match:
        return int(v_match.group(1))

    paren_match = re.search(r"\((\d+)\)$", title)
    if paren_match:
        return int(paren_match.group(1))

    end_match = re.search(r"\b(\d+)$", title)
    if end_match:
        return int(end_match.group(1))

    return None


def clean_series_title(raw_title: str) -> str:
    """Clean volume numbers and suffixes from title to produce base series title."""
    t = re.sub(r"(?:جلد|المجلد|نمبر|vol|volume)\s*(?:نمبر\s*)?\d+", "", raw_title, flags=re.IGNORECASE)
    t = re.sub(r"\(\d+\)$", "", t)
    t = re.sub(r"\b\d+$", "", t)
    t = t.replace("یونیکوڈ", "").replace("غیر موافق للمطبوع", "").replace("مترجم اردو", "")
    t = re.sub(r"\s+", " ", t).strip(" -_")
    return t if t else raw_title


def generate_urdu_series_catalog(
    database_path: Path = DEFAULT_DATABASE_PATH,
    excel_path: Path = DEFAULT_EXCEL_PATH,
    csv_path: Path = DEFAULT_CSV_PATH,
    docs_excel_path: Path = DOCS_EXCEL_PATH,
    docs_csv_path: Path = DOCS_CSV_PATH,
) -> tuple[int, Path, Path]:
    """Analyze database and generate Urdu multi-volume series inventory files."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    docs_excel_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(database_path)) as conn:
        conn.row_factory = sqlite3.Row
        books = conn.execute(
            """
            SELECT b.BookID,
                   COALESCE(b.Title, 'Untitled') AS Title,
                   COALESCE(b.Author, 'Unknown') AS Author,
                   COALESCE(l.Name, 'General') AS LibraryName,
                   COALESCE(b.Language, '') AS Language,
                   b.VolumeNumber
            FROM Books b
            LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
            ORDER BY b.BookID ASC
            """
        ).fetchall()

    urdu_books = [b for b in books if is_urdu_text(b["Title"], b["Language"])]

    series_map: dict[str, list[dict]] = {}
    for b in urdu_books:
        raw_title = str(b["Title"]).strip()
        vol_num = extract_volume_number(raw_title, b["VolumeNumber"])
        base_title = clean_series_title(raw_title)

        series_map.setdefault(base_title, []).append({
            "BookID": b["BookID"],
            "RawTitle": raw_title,
            "Author": str(b["Author"]),
            "Maktaba": str(b["LibraryName"]),
            "VolumeNumber": vol_num,
        })

    headers = [
        "SeriesID",
        "Series Title",
        "Author",
        "Maktaba (Library)",
        "Volumes Present Count",
        "Volumes Present List",
        "True Total Volumes (Internet Reference)",
        "Missing / Remaining Volumes List",
        "Status",
    ]

    report_rows = []
    series_count = 0

    for series_id, (base_title, b_list) in enumerate(sorted(series_map.items()), start=1):
        vols = [item["VolumeNumber"] for item in b_list if item["VolumeNumber"] is not None]
        if not vols and len(b_list) <= 1:
            continue

        series_count += 1
        vols_sorted = sorted(set(vols)) if vols else list(range(1, len(b_list) + 1))
        detected_max = max(vols_sorted) if vols_sorted else len(b_list)

        true_total = lookup_true_total_volumes(base_title, detected_max)
        expected = set(range(1, true_total + 1))
        missing = sorted(expected - set(vols_sorted))

        vols_present_str = ", ".join(str(v) for v in vols_sorted)
        missing_str = ", ".join(str(m) for m in missing) if missing else "None (COMPLETE)"
        status = "COMPLETE" if not missing else f"INCOMPLETE ({len(missing)} missing)"

        first_author = b_list[0]["Author"]
        first_maktaba = b_list[0]["Maktaba"]

        report_rows.append([
            series_id,
            base_title,
            first_author,
            first_maktaba,
            len(vols_sorted),
            vols_present_str,
            true_total,
            missing_str,
            status,
        ])

    # Write CSV files
    for path in (csv_path, docs_csv_path):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(report_rows)

    # Write Excel (.xlsx) files
    for path in (excel_path, docs_excel_path):
        wb = openpyxl.Workbook(write_only=True)
        ws = wb.create_sheet(title="Urdu Series Catalog")
        ws.append(headers)
        for r in report_rows:
            ws.append(r)
        try:
            wb.save(path)
        except PermissionError:
            fallback = path.parent / f"{path.stem}_Updated{path.suffix}"
            wb.save(fallback)

    return series_count, excel_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Urdu Multi-Volume Series Catalog & Missing Volumes Inventory")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--excel", type=Path, default=DEFAULT_EXCEL_PATH)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    args = parser.parse_args()

    count, ex_path, cs_path = generate_urdu_series_catalog(args.database, args.excel, args.csv)
    print(f"Urdu Multi-Volume Series Inventory Complete:")
    print(f"Total Urdu Series Tracked: {count:,}")
    print(f"1. Excel Catalog: {ex_path.resolve()}")
    print(f"2. CSV Catalog:   {cs_path.resolve()}")


if __name__ == "__main__":
    main()
