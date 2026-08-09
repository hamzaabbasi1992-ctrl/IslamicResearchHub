import openpyxl
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

root_xlsx = Path("Urdu_Multi_Volume_Series_Catalog.xlsx")
docs_xlsx = Path("docs/urdu_multi_volume_series_report.xlsx")

def find_yellow_rows(xlsx_path: Path):
    if not xlsx_path.is_file():
        print(f"File not found: {xlsx_path}")
        return []

    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb.active

    yellow_rows = []
    for row_idx, row in enumerate(ws.iter_rows(), start=1):
        if row_idx == 1:
            continue  # Skip header
        is_yellow = False
        row_vals = [cell.value for cell in row]

        for cell in row:
            fill = cell.fill
            if fill and fill.fill_type:
                color = fill.start_color or fill.fgColor
                if color:
                    rgb = str(color.rgb or color.theme or color.indexed or "").upper()
                    if "FFFF" in rgb or "YELLOW" in rgb or rgb == "FFFF0000" or "FF" in rgb:
                        is_yellow = True
                        break

        if is_yellow or (row_vals and str(row_vals[0]).startswith("HIGHLIGHT")):
            yellow_rows.append((row_idx, row_vals))

    return yellow_rows

print(f"Checking yellow highlighted rows in root file: {root_xlsx}")
res1 = find_yellow_rows(root_xlsx)
print(f"Found {len(res1)} highlighted rows in {root_xlsx}")

print(f"\nChecking yellow highlighted rows in docs file: {docs_xlsx}")
res2 = find_yellow_rows(docs_xlsx)
print(f"Found {len(res2)} highlighted rows in {docs_xlsx}")
