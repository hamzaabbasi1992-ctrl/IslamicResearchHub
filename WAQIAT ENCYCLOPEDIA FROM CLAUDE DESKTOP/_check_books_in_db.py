import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

queries = [
    ("خطبات حکیم العصر", "SELECT BookID, Title, Author, PageCount, VolumeNumber, Category FROM Books WHERE Title LIKE '%حکیم العصر%' ORDER BY BookID"),
    ("خطبات قاسمی", "SELECT BookID, Title, Author, PageCount, VolumeNumber, Category FROM Books WHERE Title LIKE '%قاسمی%' AND Title LIKE '%خطبات%' ORDER BY BookID"),
    ("خطبات علی میاں", "SELECT BookID, Title, Author, PageCount, VolumeNumber, Category FROM Books WHERE Title LIKE '%خطبات%علی میاں%' ORDER BY BookID"),
    ("اسلام اور ہماری زندگی", "SELECT BookID, Title, Author, PageCount, VolumeNumber, Category FROM Books WHERE Title LIKE '%اسلام اور ہماری زندگی%' ORDER BY BookID")
]

for qname, qsql in queries:
    cur.execute(qsql)
    rows = cur.fetchall()
    print(f"=== {qname} in data/books.db ({len(rows)} books) ===")
    for r in rows:
        print(f"  BookID {r[0]:5d} | {r[1]:32s} | {r[2]} | Pages: {r[3]} | Vol: {r[4]} | Cat: {r[5]}")
    print()

conn.close()
