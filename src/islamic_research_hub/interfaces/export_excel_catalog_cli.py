"""High-performance exporter to generate an alphabetical Excel document (.xlsx) and CSV catalog of all 100,000+ books.

Saves directly to project root folder:
- All_Books_Alphabetical_Catalog.xlsx
- All_Books_Alphabetical_Catalog.csv
"""

import argparse
import csv
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

import openpyxl

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_EXCEL_PATH = Path("All_Books_Alphabetical_Catalog.xlsx")
DEFAULT_CSV_PATH = Path("All_Books_Alphabetical_Catalog.csv")


def export_books_to_excel_and_csv(
    database_path: Path = DEFAULT_DATABASE_PATH,
    excel_path: Path = DEFAULT_EXCEL_PATH,
    csv_path: Path = DEFAULT_CSV_PATH,
) -> tuple[int, Path, Path]:
    """Export all 100,000+ books sorted alphabetically into Excel (.xlsx) and CSV format."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    with closing(sqlite3.connect(database_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT b.BookID,
                   COALESCE(b.Title, 'Untitled') AS Title,
                   COALESCE(b.Author, 'Unknown') AS Author,
                   COALESCE(l.Name, 'General') AS LibraryName,
                   COALESCE(b.Category, 'General') AS Category,
                   COALESCE(b.PageCount, 0) AS PageCount
            FROM Books b
            LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
            ORDER BY b.Title COLLATE NOCASE ASC
            """
        ).fetchall()

    headers = ["ID", "Title", "Author", "Maktaba", "Type / Category", "Pages Count"]

    # 1. Fast Stream Write Excel (.xlsx)
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet(title="Alphabetical Catalog")
    ws.append(headers)

    # 2. Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(headers)

        for row in rows:
            book_id = row["BookID"]
            title = str(row["Title"])
            author = str(row["Author"])
            maktaba = str(row["LibraryName"])
            category = str(row["Category"])
            if row["PageCount"] > 0:
                page_count_str = str(row["PageCount"])
            elif "PDF" in maktaba or "Bayanat" in maktaba:
                page_count_str = "PDF Archive"
            else:
                page_count_str = "N/A"

            record = [book_id, title, author, maktaba, category, page_count_str]
            ws.append(record)
            writer.writerow(record)

    try:
        wb.save(excel_path)
    except PermissionError:
        fallback_path = excel_path.parent / f"{excel_path.stem}_Updated{excel_path.suffix}"
        LOGGER.warning("Permission denied for %s (file is open in Excel). Saving to %s", excel_path, fallback_path)
        wb.save(fallback_path)
        excel_path = fallback_path

    return len(rows), excel_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export alphabetical book catalog to Excel (.xlsx) and CSV")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--excel", type=Path, default=DEFAULT_EXCEL_PATH)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    args = parser.parse_args()

    count, excel_out, csv_out = export_books_to_excel_and_csv(args.database, args.excel, args.csv)
    print(f"Successfully exported {count:,} books alphabetically to:")
    print(f"1. Excel: {excel_out.resolve()}")
    print(f"2. CSV:   {csv_out.resolve()}")


if __name__ == "__main__":
    main()
