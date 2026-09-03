import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

# Check EventCandidates for Taqi Usmani
cur.execute("""
    SELECT ec.BookID, b.Title, COUNT(*)
    FROM EventCandidates ec
    JOIN Books b ON ec.BookID = b.BookID
    WHERE b.Title LIKE '%تقی%' OR b.Author LIKE '%تقی%' OR b.Title LIKE '%اصلاحی خطبات%'
    GROUP BY ec.BookID, b.Title
""")
rows = cur.fetchall()
print(f"EventCandidates matching Taqi Usmani / Islahi Khutbat: {len(rows)}")
for r in rows:
    print(r)

conn.close()
