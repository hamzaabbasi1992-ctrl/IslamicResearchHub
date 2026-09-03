import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()
cur.execute("SELECT BookID, Title, PageCount FROM Books WHERE Title LIKE '%خطبات فقیر%' ORDER BY BookID")
rows = cur.fetchall()

print(f"Total Khutbat Faqeer entries in Books table: {len(rows)}")
for r in rows:
    print(f"  BookID: {r[0]:6d} | Title: {r[1]:45s} | PageCount: {r[2]}")
conn.close()
