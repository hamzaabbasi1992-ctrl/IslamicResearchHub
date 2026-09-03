import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

cur.execute("SELECT PageNo, LENGTH(Content) FROM Pages WHERE BookID=3392 ORDER BY PageNo LIMIT 30")
rows = cur.fetchall()
print(f"Sample Pages for BookID 3392 (First 30 rows):")
for r in rows:
    print(f"  PageNo: {r[0]:3d} | Length: {r[1]}")

conn.close()
