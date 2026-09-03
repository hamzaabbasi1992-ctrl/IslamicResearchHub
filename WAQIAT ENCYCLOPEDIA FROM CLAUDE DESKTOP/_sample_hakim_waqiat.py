import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

cur.execute("""
    SELECT b.Title, ec.ChunkStartPage, ec.ExtractedDataJson
    FROM EventCandidates ec
    JOIN Books b ON ec.BookID = b.BookID
    WHERE ec.BookID IN (5091, 5102) AND ec.Status = 'confirmed'
    ORDER BY ec.BookID, ec.ChunkStartPage
    LIMIT 10
""")
rows = cur.fetchall()
conn.close()

print("=" * 85)
print(" SAMPLE EXTRACTED WAQIAT FROM خطباتِ حکیم الاسلام (جلد ۱ و ۲)")
print("=" * 85)

for i, (btitle, pno, data_json) in enumerate(rows, 1):
    data = json.loads(data_json) if data_json else {}
    title = data.get('title')
    excerpt = data.get('quoted_excerpt', '')[:120].replace('\n', ' ')
    print(f"\n[{i:02d}] ✦ {title}")
    print(f"     ماخذ: {btitle}، صفحہ {pno}")
    print(f"     متن: {excerpt}...")
