import sqlite3, json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

# Audit 1: trigger phrase presence in sampled excerpts
print("=== TEXT QUALITY: Trigger phrase present in excerpt? ===")
triggers = ["ایک مرتبہ", "ایک دفعہ", "ایک بار", "منقول ہے", "روایت ہے", "ایک بزرگ", "ایک شخص", "واقعہ ہے"]

samples = cur.execute("""
    SELECT ExtractedDataJson FROM EventCandidates
    WHERE BookID BETWEEN 72 AND 106 AND Status='confirmed'
    ORDER BY RANDOM() LIMIT 200
""").fetchall()

has_trigger = 0
no_trigger = 0
no_trigger_examples = []
for (dj,) in samples:
    d = json.loads(dj) if dj else {}
    exc = d.get("quoted_excerpt") or d.get("background") or ""
    if any(t in exc for t in triggers):
        has_trigger += 1
    else:
        no_trigger += 1
        if len(no_trigger_examples) < 3:
            no_trigger_examples.append(exc[:100])

print(f"  Sample: 200 random records from Malfoozat books")
print(f"  Has narrative trigger phrase: {has_trigger} ({has_trigger/2:.1f}%)")
print(f"  No trigger phrase in excerpt: {no_trigger} ({no_trigger/2:.1f}%)")
if no_trigger_examples:
    print("  Examples WITHOUT trigger phrase (may be noise):")
    for ex in no_trigger_examples:
        print(f"    -> {ex}")
print()

# Audit 2: average excerpt length
row = cur.execute("""
    SELECT AVG(LENGTH(ExtractedDataJson))
    FROM EventCandidates
    WHERE BookID BETWEEN 72 AND 106 AND Status='confirmed'
""").fetchone()
print(f"=== AVG JSON size (Malfoozat): {row[0]:.0f} bytes ===")
print()

# Audit 3: short/garbage records (< 200 bytes in json)
short_count = cur.execute("""
    SELECT COUNT(*) FROM EventCandidates
    WHERE BookID BETWEEN 72 AND 106 AND Status='confirmed'
    AND LENGTH(ExtractedDataJson) < 200
""").fetchone()[0]
print(f"=== SHORT RECORDS (<200 bytes JSON): {short_count} ===")
if short_count > 0:
    short_samples = cur.execute("""
        SELECT BookID, ChunkStartPage, ExtractedDataJson FROM EventCandidates
        WHERE BookID BETWEEN 72 AND 106 AND Status='confirmed'
        AND LENGTH(ExtractedDataJson) < 200 LIMIT 3
    """).fetchall()
    for bid, pg, dj in short_samples:
        print(f"  BookID={bid}, Page={pg}: {dj}")
print()

# Audit 4: Web app sync
js_path = r"F:\ISLAMIC RESEARCH HUB AI\WAQIAT ENCYCLOPEDIA FROM CLAUDE DESKTOP\SEARCH APP\data.js"
if os.path.exists(js_path):
    size_mb = os.path.getsize(js_path) / 1024 / 1024
    print(f"=== WEB APP data.js size: {size_mb:.2f} MB ===")
    with open(js_path, encoding="utf-8", errors="ignore") as f:
        head = f.read(300)
    print(f"  Preview: {head[:300]}")
else:
    print("WARNING: data.js NOT FOUND")
print()

# Audit 5: Mobile JSON sync
mob_path = r"F:\ISLAMIC RESEARCH HUB AI\mobile\app\src\main\assets\waqiat_database.json"
if os.path.exists(mob_path):
    mob_size = os.path.getsize(mob_path) / 1024 / 1024
    print(f"=== MOBILE waqiat_database.json size: {mob_size:.2f} MB ===")
    with open(mob_path, encoding="utf-8", errors="ignore") as f:
        data = json.load(f)
    print(f"  Record count in JSON: {len(data)}")
else:
    print("WARNING: Mobile JSON NOT FOUND")

conn.close()
print()
print("=== QUALITY AUDIT COMPLETE ===")
