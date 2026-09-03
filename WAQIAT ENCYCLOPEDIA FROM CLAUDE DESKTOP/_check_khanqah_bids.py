import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

cur.execute("SELECT BookID, Title, Author, PageCount FROM Books WHERE Title LIKE '%اعتکاف%' OR Title LIKE '%خانقاہ%' OR Title LIKE '%غفوریہ%' OR Title LIKE '%اتوار%'")
rows = cur.fetchall()

print(f"Total matching books in Books table: {len(rows)}")
for r in rows:
    print(f"  BookID: {r[0]:6d} | Title: {r[1]:45s} | Author: {r[2]}")

conn.close()
