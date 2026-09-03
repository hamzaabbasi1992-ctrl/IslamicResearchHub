import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()
cur.execute("SELECT Title, ExtractedDataJson, BookID FROM EventCandidates WHERE BookID IN (95001, 95002) LIMIT 8")
rows = cur.fetchall()
conn.close()

print("=" * 85)
print(" SAMPLES OF CLEANED, PURE NARRATIVE WAQIAT (MAWAIZ-E-SHAMSIA)")
print("=" * 85)

for i, (title, djson, bid) in enumerate(rows, 1):
    data = json.loads(djson)
    matn = data.get("quoted_excerpt") or ""
    cit = data.get("citation") or ""
    print(f"✦ واقعہ نمبر {i}: {title}")
    print(f"  حوالہ: {cit}")
    print(f"  متن: {matn[:160]}...\n")
