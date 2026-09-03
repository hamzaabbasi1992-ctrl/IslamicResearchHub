import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

CATALOG_PATH = r"F:\ISLAMIC RESEARCH HUB AI\mobile\app\src\main\assets\catalog.db"
conn = sqlite3.connect(CATALOG_PATH)
cur = conn.cursor()

searches = ['حکیم العصر', 'قاسمی', 'اسلام اور ہماری زندگی', 'علی میاں']
for s in searches:
    cur.execute("SELECT BookID, LibraryID, Title, Author, Category, PageCount, VolumeNumber FROM Books WHERE Title LIKE ? OR Author LIKE ?", (f'%{s}%', f'%{s}%'))
    rows = cur.fetchall()
    print(f"=== Search: '{s}' in mobile catalog.db ({len(rows)} found) ===")
    for r in rows:
        print(f"  BookID {r[0]} | LibID {r[1]} | {r[2]} | {r[3]} | Cat: {r[4]} | Pages: {r[5]} | Vol: {r[6]}")
    print()

conn.close()
