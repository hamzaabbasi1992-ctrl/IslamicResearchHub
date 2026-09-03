import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()
cur.execute("SELECT Title, ExtractedDataJson FROM EventCandidates WHERE BookID=4362 AND Status='confirmed'")
rows = cur.fetchall()
conn.close()

print(f"Total confirmed Waqiat in Islahi Taqreerain Volume 2: {len(rows)}\n")
for i, (t, dj) in enumerate(rows[:10], 1):
    data = json.loads(dj)
    ex = data.get("quoted_excerpt") or ""
    cit = data.get("citation") or ""
    print(f"✦ واقعہ نمبر {i}: {t}")
    print(f"  حوالہ: {cit}")
    print(f"  متن: {ex[:160]}...\n")
