import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

CATALOG_PATH = r"F:\ISLAMIC RESEARCH HUB AI\mobile\app\src\main\assets\catalog.db"
BOOKS_DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

print("=" * 85)
print(" INSPECTING CATALOG.DB IN MOBILE ASSETS")
print("=" * 85)

conn_cat = sqlite3.connect(CATALOG_PATH)
cur_cat = conn_cat.cursor()
cur_cat.execute("SELECT name FROM sqlite_master WHERE type='table'")
cat_tables = [r[0] for r in cur_cat.fetchall()]
print(f"Tables in catalog.db: {cat_tables}")

for t in cat_tables:
    cur_cat.execute(f"SELECT COUNT(*) FROM {t}")
    cnt = cur_cat.fetchone()[0]
    print(f"  Table '{t}': {cnt} rows")

print("\n--- Books in catalog.db (Search for recent books) ---")
cur_cat.execute("SELECT book_id, title, author, category FROM books WHERE title LIKE '%حکیم العصر%' OR title LIKE '%قاسمی%' OR title LIKE '%اسلام اور ہماری زندگی%' OR title LIKE '%علی میاں%'")
rows = cur_cat.fetchall()
print(f"Matching books in mobile catalog.db: {len(rows)}")
for r in rows:
    print(f"  ID: {r[0]} | Title: {r[1]} | Author: {r[2]} | Cat: {r[3]}")

conn_cat.close()

print("\n" + "=" * 85)
print(" INSPECTING DATA/BOOKS.DB (DESKTOP MAIN LIBRARY)")
print("=" * 85)

conn_b = sqlite3.connect(BOOKS_DB_PATH)
cur_b = conn_b.cursor()
cur_b.execute("SELECT BookID, Title, Author, Category, PageCount, VolumeNumber FROM Books WHERE Title LIKE '%حکیم العصر%' OR Title LIKE '%قاسمی%' OR Title LIKE '%اسلام اور ہماری زندگی%' OR Title LIKE '%علی میاں%'")
rows_b = cur_b.fetchall()
print(f"Matching books in data/books.db: {len(rows_b)}")
for r in rows_b:
    print(f"  ID: {r[0]} | Title: {r[1]} | Author: {r[2]} | Cat: {r[3]} | Pages: {r[4]} | Vol: {r[5]}")

conn_b.close()
