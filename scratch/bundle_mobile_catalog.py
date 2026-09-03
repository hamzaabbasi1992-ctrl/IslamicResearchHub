import shutil
import sqlite3
from pathlib import Path

src_cat = Path("data/exports/catalog.db")
assets_dir = Path("mobile/app/src/main/assets")
assets_dir.mkdir(parents=True, exist_ok=True)
dest_cat = assets_dir / "catalog.db"

if src_cat.is_file():
    shutil.copy2(src_cat, dest_cat)
    with sqlite3.connect(dest_cat) as connection:
        book_count = connection.execute("SELECT COUNT(*) FROM Books").fetchone()[0]
    print(f"Bundled {book_count:,} books mobile catalog.db into app assets: {dest_cat.resolve()}")
    print(f"Asset file size: {dest_cat.stat().st_size / (1024*1024):.2f} MB")
else:
    print("Source catalog.db not found.")
