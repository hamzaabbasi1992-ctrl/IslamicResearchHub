import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
rows = conn.execute("""
    SELECT ec.BookID, b.Title, COUNT(*)
    FROM EventCandidates ec
    JOIN Books b ON ec.BookID = b.BookID
    WHERE ec.BookID BETWEEN 3601 AND 3612 AND ec.Status='confirmed'
    GROUP BY ec.BookID, b.Title
    ORDER BY ec.BookID
""").fetchall()

print("=" * 85)
print(" KHUTBAT HAKEEM-UL-ASR CONFIRMED WAQIAT BREAKDOWN ACROSS ALL 12 VOLUMES")
print("=" * 85)
total = 0
for bid, title, cnt in rows:
    total += cnt
    print(f"  BookID {bid:5d} | {title:32s} | {cnt:3d} Waqiat")
print("-" * 85)
print(f"  TOTAL CONFIRMED WAQIAT FOR KHUTBAT HAKEEM-UL-ASR: {total}")
print("=" * 85)

cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'")
grand_total = cur.fetchone()[0]
print(f"  🌟 GRAND TOTAL MASTER LIBRARY DATABASE NOW: {grand_total} PURE CONFIRMED WAQIAT")
print("=" * 85)
conn.close()
