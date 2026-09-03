import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
rows = conn.execute("SELECT BookID, Title, VolumeNumber, PageCount FROM Books WHERE Title LIKE '%خطبات قاسمی%جلد 3%' OR Title LIKE '%خطبات قاسمی%جلد 4%'").fetchall()
print("Search for Vol 3 and 4 in Books table:")
for r in rows:
    print(" ", r)
conn.close()
