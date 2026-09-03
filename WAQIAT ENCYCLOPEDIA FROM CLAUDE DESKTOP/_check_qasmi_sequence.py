import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
rows = conn.execute("SELECT BookID, Title, VolumeNumber, PageCount FROM Books WHERE BookID BETWEEN 3530 AND 3585 ORDER BY BookID").fetchall()
for r in rows:
    print(f"  BookID {r[0]:5d} | Vol: {str(r[2]):4s} | Pgs: {str(r[3]):4s} | Title: {r[1]}")
conn.close()
