import sqlite3, json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
    SELECT EventCandidateID, BookID, Title, ExtractedDataJson
    FROM EventCandidates
    WHERE BookID IN (95001, 95002) AND Status='confirmed'
""")
rows = cur.fetchall()
conn.close()

print(f"Total extracted items in Mawaiz Shamsia: {len(rows)}")

irshad_count = 0
short_quotes = []
genuine_waqiat = []

for r in rows:
    ev_id, bid, title, data_json = r
    try:
        data = json.loads(data_json)
    except:
        continue
    matn = data.get("quoted_excerpt") or data.get("background") or ""
    
    # Check if it starts with generic irshad/farmaya without narrative
    is_generic_quote = False
    if any(title.strip().startswith(p) for p in ["ارشاد فرمایا", "فرمایا کہ", "بیان فرمایا", "لکھا ہے کہ", "آیا ہے کہ"]):
        is_generic_quote = True
        irshad_count += 1
        short_quotes.append((title, matn[:120]))
    else:
        # Check narrative depth
        genuine_waqiat.append((title, matn[:120]))

print(f"\n❌ Generic Quotes / Non-Waqiat (Starting with ارشاد فرمایا / فرمایا کہ etc.): {irshad_count}")
print(f"✅ Genuine Narrative Candidates: {len(genuine_waqiat)}")

print("\n--- SAMPLE 10 GENERIC QUOTES (TO BE REMOVED) ---")
for t, m in short_quotes[:10]:
    print(f"  ❌ عنوان: {t}")
    print(f"     متن: {m}...\n")

print("\n--- SAMPLE 10 GENUINE WAQIAT (TO BE RETAINED) ---")
for t, m in genuine_waqiat[:10]:
    print(f"  ✅ عنوان: {t}")
    print(f"     متن: {m}...\n")
