import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

cur.execute("SELECT BookID, Title, Author, PageCount, VolumeNumber FROM Books WHERE Title LIKE '%حکیم الاسلام%' OR Title LIKE '%طیب%' ORDER BY BookID")
rows = cur.fetchall()

print(f"Total matching books found: {len(rows)}")
for r in rows:
    print(f"  BookID: {r[0]:6d} | Title: {r[1]:45s} | Author: {r[2]} | PageCount: {r[3]} | Vol: {r[4]}")

conn.close()
