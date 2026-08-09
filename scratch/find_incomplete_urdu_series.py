import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

csv_path = Path("Urdu_Multi_Volume_Series_Catalog.csv")

if not csv_path.is_file():
    print("CSV file not found")
    sys.exit(1)

incomplete_series = []

with open(csv_path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        status = row["Status"]
        if "INCOMPLETE" in status or row["Missing / Remaining Volumes"] != "None (COMPLETE)":
            incomplete_series.append(row)

print(f"Total Incomplete / Partial Urdu Series Found: {len(incomplete_series):,}\n")
print("Top 30 Incomplete Urdu Series Needing True Internet Volume Counts:")
for idx, item in enumerate(incomplete_series[:30], start=1):
    print(f"  {idx}. '{item['Series Title']}' | Author: {item['Author']}")
    print(f"     - Volumes Present: {item['Total Volumes Present']} (Vols: {item['Volumes Present List']})")
    print(f"     - Missing in Library: {item['Missing / Remaining Volumes']}\n")
