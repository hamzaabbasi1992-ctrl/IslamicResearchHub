import os, sys, sqlite3
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"F:\ISLAMIC RESEARCH HUB AI\src")

from islamic_research_hub.interfaces.catalog_export_cli import export_catalog_to_file
from islamic_research_hub.interfaces.book_package_export_cli import export_book_package_to_file

DB_PATH = Path(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
MOBILE_ASSETS_DIR = Path(r"F:\ISLAMIC RESEARCH HUB AI\mobile\app\src\main\assets")
MOBILE_CATALOG_PATH = MOBILE_ASSETS_DIR / "catalog.db"
SAMPLE_BOOKS_DIR = MOBILE_ASSETS_DIR / "sample_books"
SAMPLE_BOOKS_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 85)
print(" 1. ENRICHING BOOKS METADATA IN DATA/BOOKS.DB")
print("=" * 85)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 1. Update Khutbat Hakeem-ul-Asr (BookIDs 3601 to 3612)
for v in range(1, 13):
    bid = 3600 + v
    cur.execute("""
        UPDATE Books
        SET LibraryID=2, Publisher='مکتبہ باب العلوم، کہروڑ پکا',
            Category='خطبات و مواعظ', SeriesID=3600, VolumeNumber=?
        WHERE BookID=?
    """, (v, bid))

# 2. Update Khutbat Qasmi (BookIDs 3534, 3545, 35451, 35452, 3556, 3567)
qasmi_vols = [(1, 3534), (2, 3545), (3, 35451), (4, 35452), (5, 3556), (6, 3567)]
for v, bid in qasmi_vols:
    cur.execute("""
        UPDATE Books
        SET LibraryID=2, Publisher='مکتبہ قاسم العلوم، فیصل آباد',
            Category='خطبات و مواعظ', SeriesID=3534, VolumeNumber=?
        WHERE BookID=?
    """, (v, bid))

# 3. Update Islam aur Hamari Zindagi (BookIDs 3392, 3465, 3523, 3633, 3744, 3854, 3961, 4051, 4146, 4251)
islam_vols = [
    (1, 3392), (2, 3465), (3, 3523), (4, 3633), (5, 3744),
    (6, 3854), (7, 3961), (8, 4051), (9, 4146), (10, 4251)
]
for v, bid in islam_vols:
    cur.execute("""
        UPDATE Books
        SET LibraryID=2, Publisher='میمن اسلامک پبلشرز، کراچی',
            Category='خطبات و مواعظ', SeriesID=3392, VolumeNumber=?
        WHERE BookID=?
    """, (v, bid))

# 4. Update Khutbat Ali Mian (BookIDs 3274, 3284, 3294, 3305, 3316, 3327, 3336)
ali_mian_vols = [
    (1, 3274), (2, 3284), (3, 3294), (4, 3305), (5, 3316), (6, 3327), (7, 3336)
]
for v, bid in ali_mian_vols:
    cur.execute("""
        UPDATE Books
        SET LibraryID=2, Publisher='مجلس نشریات اسلام، کراچی',
            Category='خطبات و مواعظ', SeriesID=3274, VolumeNumber=?
        WHERE BookID=?
    """, (v, bid))

conn.commit()
conn.close()
print("✅ Desktop database metadata updated successfully!")

print("\n" + "=" * 85)
print(" 2. EXPORTING UPDATED CATALOG.DB FOR MOBILE APP")
print("=" * 85)

# Export catalog.db to mobile assets
export_catalog_to_file(DB_PATH, MOBILE_CATALOG_PATH)
cat_size_mb = MOBILE_CATALOG_PATH.stat().st_size / (1024 * 1024)
print(f"✅ Exported mobile catalog: {MOBILE_CATALOG_PATH} ({cat_size_mb:.2f} MB)")

# Also export to data/exports/catalog.db
export_catalog_to_file(DB_PATH, Path("data/exports/catalog.db"))

print("\n" + "=" * 85)
print(" 3. EXPORTING FULL BOOK PACKAGES (BOOK_*.DB) FOR MOBILE READER")
print("=" * 85)

# Export offline packages for key volumes
packages_to_export = [
    (3392, "اسلام اور ہماری زندگی جلد 1"),
    (3601, "خطبات حکیم العصر جلد 1"),
    (3534, "خطبات قاسمی جلد 1"),
    (3274, "خطبات علی میاں جلد 1")
]

for bid, bname in packages_to_export:
    out_pkg = SAMPLE_BOOKS_DIR / f"book_{bid}.db"
    try:
        export_book_package_to_file(DB_PATH, bid, out_pkg)
        pkg_size_mb = out_pkg.stat().st_size / (1024 * 1024)
        print(f"  ✅ Exported Package: book_{bid}.db ({bname}) -> {pkg_size_mb:.2f} MB")
    except Exception as e:
        print(f"  ❌ Error exporting book_{bid}.db: {e}")

print("\n" + "=" * 85)
print(" ALL LIBRARY DATA & MOBILE ASSETS UPDATED SUCCESSFULLY!")
print("=" * 85)
