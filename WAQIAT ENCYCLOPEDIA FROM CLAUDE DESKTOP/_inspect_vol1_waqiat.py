import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
    SELECT ChunkStartPage, ExtractedDataJson
    FROM EventCandidates
    WHERE BookID = 3358 AND Status = 'confirmed'
    ORDER BY ChunkStartPage
""")
rows = cur.fetchall()
conn.close()

print("=" * 85)
print(f" EXTRACTED WAQIAT FROM خطبات فقیر — جلد 1 ({len(rows)} Waqiat)")
print("=" * 85)

for i, (pno, data_json) in enumerate(rows[:25], 1):
    data = json.loads(data_json) if data_json else {}
    title = data.get('title')
    excerpt = data.get('quoted_excerpt', '')[:120].replace('\n', ' ')
    cit = data.get('citation')
    print(f"\n[{i:02d}] ✦ {title}")
    print(f"     حوالہ: {cit}")
    print(f"     متن: {excerpt}...")
