"""CLI & Engine to generate master Library Inventory & Statistical Reports.

Generates:
1. docs/library_report.md
2. docs/library_report.json
3. Library_Inventory_Summary.xlsx
4. Library_Inventory_Summary.csv
"""

import argparse
import csv
import json
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

import openpyxl

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_MD_REPORT = Path("docs/library_report.md")
DEFAULT_JSON_REPORT = Path("docs/library_report.json")
DEFAULT_EXCEL_REPORT = Path("Library_Inventory_Summary.xlsx")
DEFAULT_CSV_REPORT = Path("Library_Inventory_Summary.csv")


def generate_library_reports(
    database_path: Path = DEFAULT_DATABASE_PATH,
    md_path: Path = DEFAULT_MD_REPORT,
    json_path: Path = DEFAULT_JSON_REPORT,
    excel_path: Path = DEFAULT_EXCEL_REPORT,
    csv_path: Path = DEFAULT_CSV_REPORT,
) -> tuple[int, int, int, int]:
    """Calculate statistics per library and export all report formats."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    md_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(database_path)) as conn:
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

    total_books_sum = sum(r["TotalBooks"] for r in rows)
    total_text_sum = sum(r["TextBooksCount"] for r in rows)
    total_pdf_sum = sum(r["PDFArchiveBooksCount"] for r in rows)
    total_pages_sum = sum(r["TotalPagesCount"] for r in rows)

    headers = [
        "Maktaba (Library) Name",
        "Primary Format Type",
        "Total Books",
        "Searchable Text Books",
        "Scanned PDF / Audio Archives",
        "Total Pages Count",
    ]

    report_data = []
    json_libraries = []

    for r in rows:
        lib_name = r["LibraryName"] or "Unknown"
        is_pdf = "PDF" in lib_name or "Bayanat" in lib_name
        fmt_type = "Scanned PDF / Audio" if is_pdf else "Searchable Text"

        record = [
            lib_name,
            fmt_type,
            r["TotalBooks"],
            r["TextBooksCount"],
            r["PDFArchiveBooksCount"],
            r["TotalPagesCount"],
        ]
        report_data.append(record)

        json_libraries.append({
            "library_name": lib_name,
            "format_type": fmt_type,
            "total_books": r["TotalBooks"],
            "searchable_text_books": r["TextBooksCount"],
            "pdf_archive_books": r["PDFArchiveBooksCount"],
            "total_pages": r["TotalPagesCount"],
        })

    # 1. Write CSV Summary
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(headers)
        writer.writerows(report_data)
        writer.writerow([
            "TOTAL MASTER INVENTORY",
            "Summary",
            total_books_sum,
            total_text_sum,
            total_pdf_sum,
            total_pages_sum,
        ])

    # 2. Write Excel (.xlsx) Summary
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet(title="Library Inventory")
    ws.append(headers)
    for r in report_data:
        ws.append(r)
    ws.append([
        "TOTAL MASTER INVENTORY",
        "Summary",
        total_books_sum,
        total_text_sum,
        total_pdf_sum,
        total_pages_sum,
    ])
    try:
        wb.save(excel_path)
    except PermissionError:
        excel_path = excel_path.parent / f"{excel_path.stem}_Updated{excel_path.suffix}"
        wb.save(excel_path)

    # 3. Write JSON Report
    json_output = {
        "master_summary": {
            "total_books": total_books_sum,
            "searchable_text_books": total_text_sum,
            "pdf_archive_books": total_pdf_sum,
            "total_pages": total_pages_sum,
        },
        "libraries": json_libraries,
    }
    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(json_output, f_json, indent=2, ensure_ascii=False)

    # 4. Write Markdown Report (docs/library_report.md)
    with open(md_path, "w", encoding="utf-8") as f_md:
        f_md.write("# Master Library Inventory & Statistical Report\n\n")
        f_md.write("Comprehensive statistics breaking down total books, searchable text volumes, scanned PDF/audio archives, and total page counts per Maktaba.\n\n")

        f_md.write("> [!NOTE]\n")
        f_md.write(f"> **Master Summary**: **{total_books_sum:,} Books** | **{total_text_sum:,} Searchable Text** | **{total_pdf_sum:,} PDF/Audio Archives** | **{total_pages_sum:,} Total Pages**\n\n")

        f_md.write("| Maktaba (Library) Name | Primary Format Type | Total Books | Searchable Text Books | Scanned PDF / Audio Archives | Total Pages Count |\n")
        f_md.write("| :--- | :--- | :---: | :---: | :---: | :---: |\n")

        for r in report_data:
            f_md.write(f"| **{r[0]}** | {r[1]} | **{r[2]:,}** | {r[3]:,} | {r[4]:,} | **{r[5]:,}** |\n")

        f_md.write(f"| **TOTAL MASTER INVENTORY** | **Summary** | **{total_books_sum:,}** | **{total_text_sum:,}** | **{total_pdf_sum:,}** | **{total_pages_sum:,}** |\n")

    return total_books_sum, total_text_sum, total_pdf_sum, total_pages_sum


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Master Library Inventory Summary Reports")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    args = parser.parse_args()

    tb, txt, pdf, pgs = generate_library_reports(args.database)
    print("Master Library Inventory Report Generated:")
    print(f"Total Books:    {tb:,}")
    print(f"Text Books:     {txt:,}")
    print(f"PDF/Audio:      {pdf:,}")
    print(f"Total Pages:    {pgs:,}")


if __name__ == "__main__":
    main()
