import sqlite3, json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

# Check Volume 1 Waqiat with PageNo >= 20
cur.execute("SELECT ChunkStartPage, Title, ExtractedDataJson FROM EventCandidates WHERE BookID=3392 AND Status='confirmed' AND ChunkStartPage >= 20 ORDER BY ChunkStartPage")
rows = cur.fetchall()

print(f"Volume 1 Genuine Waqiat (PageNo >= 20): {len(rows)}\n")
for pno, t, dj in rows[:15]:
    data = json.loads(dj)
    ex = data.get('quoted_excerpt') or ''
    print(f"✦ صفحہ {pno}: {t}")
    print(f"   متن: {ex[:140]}...\n")

conn.close()
