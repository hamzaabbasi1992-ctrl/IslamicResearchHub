import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

# Let's compare the speeches / chapters of 'اسلام اور ہماری زندگی جلد 1' vs 'اصلاحی خطبات جلد 1'
cur.execute("SELECT Content FROM Pages WHERE BookID=3392 AND PageNo BETWEEN 22 AND 35")
islam_pages = [r[0] for r in cur.fetchall() if r[0]]

cur.execute("SELECT Title, ExtractedDataJson FROM EventCandidates WHERE BookID=322 LIMIT 30")
islahi_entries = cur.fetchall()

print("=== SPEECH TITLES IN ISLAHI KHUTBAT VOL 1 ===")
for t, dj in islahi_entries[:15]:
    print(" ", t)

print("\n=== SAMPLE CONTENT IN ISLAM AUR HAMARI ZINDAGI VOL 1 ===")
for p in islam_pages[:3]:
    lines = [l.strip() for l in p.split('\n') if l.strip()]
    print("  First 3 lines of page:")
    for l in lines[:3]:
        print("    ", l)

conn.close()
