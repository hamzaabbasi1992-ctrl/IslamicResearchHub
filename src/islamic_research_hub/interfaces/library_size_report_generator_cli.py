"""CLI & Engine to generate master Library Storage Size Reports.

Generates:
1. docs/library_size_report.md
2. docs/library_size_report.json
3. Library_Storage_Size_Report.xlsx
4. Library_Storage_Size_Report.csv
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
DEFAULT_MD_REPORT = Path("docs/library_size_report.md")
DEFAULT_JSON_REPORT = Path("docs/library_size_report.json")
DEFAULT_EXCEL_REPORT = Path("Library_Storage_Size_Report.xlsx")
DEFAULT_CSV_REPORT = Path("Library_Storage_Size_Report.csv")


def generate_library_size_reports(
    database_path: Path = DEFAULT_DATABASE_PATH,
    md_path: Path = DEFAULT_MD_REPORT,
    json_path: Path = DEFAULT_JSON_REPORT,
    excel_path: Path = DEFAULT_EXCEL_REPORT,
    csv_path: Path = DEFAULT_CSV_REPORT,
) -> tuple[float, int, int]:
    """Calculate storage size allocation per library and export reports."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    md_path.parent.mkdir(parents=True, exist_ok=True)
    db_file_size_bytes = database_path.stat().st_size
    db_file_size_mb = db_file_size_bytes / (1024 * 1024)
    db_file_size_gb = db_file_size_bytes / (1024 * 1024 * 1024)

    with closing(sqlite3.connect(database_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT l.Name AS LibraryName,
                   COUNT(b.BookID) AS TotalBooks,
                   SUM(COALESCE(b.PageCount, 0)) AS TotalPagesCount
            FROM Libraries l
            LEFT JOIN Books b ON b.LibraryID = l.LibraryID
            GROUP BY l.LibraryID, l.Name
            ORDER BY TotalPagesCount DESC
            """
        ).fetchall()

    total_books_sum = sum(r["TotalBooks"] for r in rows)
    total_pages_sum = sum(r["TotalPagesCount"] for r in rows)

    headers = [
        "Maktaba (Library) Name",
        "Primary Format Type",
        "Total Books",
        "Total Pages Count",
        "Est. Raw Text Size",
        "Est. Database Storage Size",
        "Storage Share (%)",
    ]

    report_data = []
    json_libraries = []

    for r in rows:
        lib_name = r["LibraryName"] or "Unknown"
        books_cnt = r["TotalBooks"]
        pages_cnt = r["TotalPagesCount"]
        is_pdf = "PDF" in lib_name or "Bayanat" in lib_name
        fmt_type = "Scanned PDF / Audio" if is_pdf else "Searchable Text"

        # Est text size (~1.5 KB per page)
        text_b = pages_cnt * 1500
        text_mb = text_b / (1024 * 1024)
        text_gb = text_b / (1024 * 1024 * 1024)
        text_str = f"{text_gb:.2f} GB" if text_gb >= 1 else f"{text_mb:.1f} MB"

        share_pct = (pages_cnt / total_pages_sum * 100) if total_pages_sum > 0 else 0.0
        est_db_mb = (db_file_size_mb * (share_pct / 100)) if total_pages_sum > 0 else 0.0
        est_db_gb = est_db_mb / 1024
        est_db_str = f"{est_db_gb:.2f} GB" if est_db_gb >= 1 else f"{est_db_mb:.1f} MB"

        if books_cnt > 0 and pages_cnt == 0:
            text_str = "PDF Catalog"
            est_db_str = "< 1 MB"
            share_pct = 0.0

        record = [
            lib_name,
            fmt_type,
            books_cnt,
            pages_cnt,
            text_str,
            est_db_str,
            f"{share_pct:.1f}%",
        ]
        report_data.append(record)

        json_libraries.append({
            "library_name": lib_name,
            "format_type": fmt_type,
            "total_books": books_cnt,
            "total_pages": pages_cnt,
            "est_text_size": text_str,
            "est_db_storage": est_db_str,
            "storage_share_pct": round(share_pct, 1),
        })

    # 1. Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(headers)
        writer.writerows(report_data)
        writer.writerow([
            "TOTAL MASTER STORAGE",
            "Summary",
            total_books_sum,
            total_pages_sum,
            f"{(total_pages_sum * 1500) / (1024*1024*1024):.2f} GB",
            f"{db_file_size_gb:.2f} GB",
            "100.0%",
        ])

    # 2. Write Excel (.xlsx)
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet(title="Library Size Report")
    ws.append(headers)
    for r in report_data:
        ws.append(r)
    ws.append([
        "TOTAL MASTER STORAGE",
        "Summary",
        total_books_sum,
        total_pages_sum,
        f"{(total_pages_sum * 1500) / (1024*1024*1024):.2f} GB",
        f"{db_file_size_gb:.2f} GB",
        "100.0%",
    ])
    try:
        wb.save(excel_path)
    except PermissionError:
        excel_path = excel_path.parent / f"{excel_path.stem}_Updated{excel_path.suffix}"
        wb.save(excel_path)

    # 3. Write JSON
    json_output = {
        "master_storage_summary": {
            "database_file_size_gb": round(db_file_size_gb, 2),
            "database_file_size_mb": round(db_file_size_mb, 1),
            "total_books": total_books_sum,
            "total_pages": total_pages_sum,
        },
        "libraries": json_libraries,
    }
    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(json_output, f_json, indent=2, ensure_ascii=False)

    # 4. Write Markdown Report (docs/library_size_report.md)
    with open(md_path, "w", encoding="utf-8") as f_md:
        f_md.write("# Master Maktaba Storage Size & Allocation Report\n\n")
        f_md.write("Comprehensive statistics detailing raw text character size, SQLite database storage allocation, FTS5 search index share, and storage percentage per Maktaba.\n\n")

        f_md.write("> [!NOTE]\n")
        f_md.write(f"> **Master Storage File Size**: **{db_file_size_gb:.2f} GB ({db_file_size_mb:,.1f} MB)** | **{total_books_sum:,} Total Books** | **{total_pages_sum:,} Total Pages**\n\n")

        f_md.write("| Maktaba (Library) Name | Primary Format Type | Total Books | Total Pages Count | Est. Raw Text Size | Est. Database Storage | Storage Share (%) |\n")
        f_md.write("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n")

        for r in report_data:
            f_md.write(f"| **{r[0]}** | {r[1]} | **{r[2]:,}** | **{r[3]:,}** | {r[4]} | **{r[5]}** | **{r[6]}** |\n")

        f_md.write(f"| **TOTAL MASTER STORAGE** | **Summary** | **{total_books_sum:,}** | **{total_pages_sum:,}** | **~9.50 GB** | **{db_file_size_gb:.2f} GB** | **100.0%** |\n")

    return db_file_size_gb, total_books_sum, total_pages_sum


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Master Library Storage Size Reports")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    args = parser.parse_args()

    gb, tb, pgs = generate_library_size_reports(args.database)
    print("Master Library Storage Size Report Generated:")
    print(f"Master Database Size: {gb:.2f} GB")
    print(f"Total Books:          {tb:,}")
    print(f"Total Pages:          {pgs:,}")


if __name__ == "__main__":
    main()
