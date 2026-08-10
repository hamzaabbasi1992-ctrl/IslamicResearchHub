import shutil
from pathlib import Path

src_cat = Path("data/exports/catalog.db")
dest_dir = Path("installation/AndroidApp")
dest_dir.mkdir(parents=True, exist_ok=True)
dest_cat = dest_dir / "catalog.db"

if src_cat.is_file():
    shutil.copy2(src_cat, dest_cat)
    print(f"Master Catalog.db copied to installation folder: {dest_cat.resolve()}")
    print(f"File size: {dest_cat.stat().st_size / (1024*1024):.2f} MB")
else:
    print("Source catalog.db not found.")
