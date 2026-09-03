import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=3392 AND Content LIKE '%بہن سے نکاح%'")
rows = cur.fetchall()
print(f"Matches for 'بہن سے نکاح' in Islam aur Hamari Zindagi Vol 1 (BookID 3392): {len(rows)}")
for pno, c in rows:
    print(f"  Page {pno}: {c[:200]}")

conn.close()
