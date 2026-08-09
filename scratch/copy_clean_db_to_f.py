import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

f_db = Path("F:/ISLAMIC RESEARCH HUB AI/data/books.db")
d_compact = Path("D:/ISLAMIC RESEARCH HUB AI/data/books_compact.db")

print(f"Copying clean 24.5 GB database to F:\\ISLAMIC RESEARCH HUB AI\\data\\books.db...")
shutil.copy2(d_compact, f_db)
print(f"Done! F: Drive books.db size: {f_db.stat().st_size / (1024*1024*1024):.2f} GB")
