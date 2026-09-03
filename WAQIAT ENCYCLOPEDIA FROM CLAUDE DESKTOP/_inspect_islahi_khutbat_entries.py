import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

# Check sample entries of Islahi Khutbat (BookID 322)
cur.execute("SELECT EventCandidateID, Title, ExtractedDataJson FROM EventCandidates WHERE BookID=322 ORDER BY ChunkStartPage LIMIT 25")
rows = cur.fetchall()

print("=" * 85)
print(" SAMPLE ENTRIES IN ISLAHI KHUTBAT (BOOKID 322 - 18 VOLUMES)")
print("=" * 85)
for eid, title, dj in rows:
    data = json.loads(dj)
    ex = data.get('quoted_excerpt') or ''
    cit = data.get('citation') or ''
    print(f"[{eid}] {title}")
    print(f"     حوالہ: {cit}")
    print(f"     متن: {repr(ex[:120])}\n")

cur.execute("SELECT COUNT(*) FROM EventCandidates WHERE BookID BETWEEN 322 AND 1705 AND Status='confirmed'")
total_islahi = cur.fetchone()[0]
print(f"Total confirmed entries in Islahi Khutbat: {total_islahi}")

conn.close()
