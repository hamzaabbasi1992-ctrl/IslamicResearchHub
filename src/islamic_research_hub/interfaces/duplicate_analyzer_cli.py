"""CLI & Engine to analyze, group, and export duplicate books in master database.

Generates:
1. docs/duplicate_books_report.xlsx
2. docs/duplicate_books_report.csv
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
DEFAULT_REPORT_XLSX = Path("docs/duplicate_books_report.xlsx")
DEFAULT_REPORT_CSV = Path("docs/duplicate_books_report.csv")


def normalize_title_key(title: str) -> str:
    """Normalize title by removing volume suffixes like (2), جلد 2, spaces, and punctuation."""
    t = str(title).strip().lower()
    # Remove disambiguation suffix (2), (3), etc.
    t = re.sub(r"\s*\(\d+\)$", "", t)
    # Remove Arabic volume prefixes like جلد 2, المجلد 2
    t = re.sub(r"\s*(جلد|المجلد|part|vol|volume)\s*\d+$", "", t)
    # Remove non-alphanumeric chars
    t = re.sub(r"[^\w\s\u0600-\u06FF]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def analyze_duplicate_books(
    database_path: Path = DEFAULT_DATABASE_PATH,
    report_xlsx: Path = DEFAULT_REPORT_XLSX,
    report_csv: Path = DEFAULT_REPORT_CSV,
) -> tuple[int, int, Path, Path]:
    """Audit master database for duplicate books and export detailed report."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    report_xlsx.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(database_path)) as conn:
        conn.row_factory = sqlite3.Row
        books = conn.execute(
            """
            SELECT b.BookID,
                   COALESCE(b.Title, 'Untitled') AS Title,
                   COALESCE(b.Author, '') AS Author,
                   COALESCE(l.Name, 'General') AS LibraryName,
                   COALESCE(b.Category, 'General') AS Category,
                   COALESCE(b.PageCount, 0) AS PageCount
            FROM Books b
            LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
            ORDER BY b.BookID ASC
            """
        ).fetchall()

    groups: dict[str, list[sqlite3.Row]] = {}
    for b in books:
        key = normalize_title_key(b["Title"])
        if key:
            groups.setdefault(key, []).append(b)

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

    headers = [
        "GroupID",
        "DuplicateType",
        "BookID",
        "Title",
        "Author",
        "Maktaba",
        "Category",
        "PageCount",
    ]

    report_rows = []
    total_duplicate_books = 0

    for group_id, (norm_key, book_list) in enumerate(sorted(duplicate_groups.items()), start=1):
        # Determine duplicate type
        titles = [b["Title"] for b in book_list]
        libraries = {b["LibraryName"] for b in book_list}

        if len(set(titles)) == 1:
            dup_type = "Exact Title Match"
        elif len(libraries) > 1:
            dup_type = "Cross-Library Duplicate"
        else:
            dup_type = "Title Variant / Disambiguated (2)"

        for b in book_list:
            total_duplicate_books += 1
            report_rows.append([
                group_id,
                dup_type,
                b["BookID"],
                b["Title"],
                b["Author"],
                b["LibraryName"],
                b["Category"],
                b["PageCount"],
            ])

    # Write CSV Report
    with open(report_csv, "w", newline="", encoding="utf-8-sig") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(headers)
        writer.writerows(report_rows)

    # Write Excel (.xlsx) Report using write_only streaming
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet(title="Duplicates Audit")
    ws.append(headers)
    for r in report_rows:
        ws.append(r)

    try:
        wb.save(report_xlsx)
    except PermissionError:
        report_xlsx = report_xlsx.parent / f"{report_xlsx.stem}_Updated{report_xlsx.suffix}"
        wb.save(report_xlsx)

    return len(duplicate_groups), total_duplicate_books, report_xlsx, report_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and export duplicate books report")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--report-xlsx", type=Path, default=DEFAULT_REPORT_XLSX)
    parser.add_argument("--report-csv", type=Path, default=DEFAULT_REPORT_CSV)
    args = parser.parse_args()

    num_groups, num_books, xlsx_out, csv_out = analyze_duplicate_books(
        args.database, args.report_xlsx, args.report_csv
    )
    print("Duplicate Books Audit Complete:")
    print(f"Total Duplicate Groups: {num_groups:,}")
    print(f"Total Duplicate Books Found: {num_books:,}")
    print(f"Excel Report: {xlsx_out.resolve()}")
    print(f"CSV Report:   {csv_out.resolve()}")


if __name__ == "__main__":
    main()
