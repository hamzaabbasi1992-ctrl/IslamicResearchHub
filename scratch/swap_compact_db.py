import os
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

f_db = Path("F:/ISLAMIC RESEARCH HUB AI/data/books.db")
d_compact = Path("D:/ISLAMIC RESEARCH HUB AI/data/books_compact.db")
d_db = Path("D:/ISLAMIC RESEARCH HUB AI/data/books.db")

print("Starting Final File Swap & Disk Space Release...")
print(f"Compact DB on D: drive size: {d_compact.stat().st_size / (1024*1024*1024):.2f} GB")

# 1. Remove old uncompacted books.db on F:
if f_db.is_file():
    print(f"Deleting old 156.5 GB books.db from F: drive...")
    f_db.unlink()

# 2. Copy clean 24.5 GB database to F:\ISLAMIC RESEARCH HUB AI\data\books.db
print(f"Copying clean 24.5 GB database to F:\\ISLAMIC RESEARCH HUB AI\\data\\books.db...")
shutil.copy2(d_compact, f_db)

# 3. Rename books_compact.db on D: to books.db
print(f"Renaming D:\\ISLAMIC RESEARCH HUB AI\\data\\books_compact.db to books.db...")
if d_db.is_file():
    d_db.unlink()
d_compact.rename(d_db)

print("File Swap Complete!")
print(f"1. F: Drive active books.db size: {f_db.stat().st_size / (1024*1024*1024):.2f} GB")
print(f"2. D: Drive backup books.db size: {d_db.stat().st_size / (1024*1024*1024):.2f} GB")
