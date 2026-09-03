import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

cur.execute("SELECT BookID, Title, Author, PageCount, VolumeNumber FROM Books WHERE Title LIKE '%تقی%' OR Author LIKE '%تقی%' OR Title LIKE '%اصلاحی خطبات%' OR Title LIKE '%اسلام اور ہماری زندگی%'")
rows = cur.fetchall()

print("Existing books of Mufti Taqi Usmani in books.db:")
for r in rows:
    # Check if there are EventCandidates
    cur.execute("SELECT COUNT(*) FROM EventCandidates WHERE BookID=?", (r[0],))
    ec_count = cur.fetchone()[0]
    print(f"  BookID {r[0]:5d} | {r[1]:40s} | {r[3]:4d} pgs | Waqiat: {ec_count}")

conn.close()
