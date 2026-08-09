import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

f_db = Path("F:/ISLAMIC RESEARCH HUB AI/data/books.db")
d_compact = Path("D:/ISLAMIC RESEARCH HUB AI/data/books_compact.db")

print(f"Copying complete, clean 24.5 GB database from D: drive to F: drive...")
shutil.copy2(d_compact, f_db)
print(f"Copy complete! F: Drive books.db size: {f_db.stat().st_size / (1024*1024*1024):.2f} GB")
