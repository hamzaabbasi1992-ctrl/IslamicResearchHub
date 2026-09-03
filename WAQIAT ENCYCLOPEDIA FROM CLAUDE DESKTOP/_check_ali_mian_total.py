import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
rows = conn.execute("""
    SELECT ec.BookID, b.Title, COUNT(*)
    FROM EventCandidates ec
    JOIN Books b ON ec.BookID = b.BookID
    WHERE ec.BookID IN (3274, 3284, 3294, 3305, 3316, 3327, 3336) AND ec.Status='confirmed'
    GROUP BY ec.BookID, b.Title
    ORDER BY ec.BookID
""").fetchall()

print("=" * 80)
print(" KHUTBAT ALI MIAN CONFIRMED WAQIAT BREAKDOWN ACROSS ALL 7 VOLUMES")
print("=" * 80)
total = 0
for bid, title, cnt in rows:
    total += cnt
    print(f"  BookID {bid:5d} | {title:35s} | {cnt:3d} Waqiat")
print("-" * 80)
print(f"  TOTAL CONFIRMED WAQIAT: {total}")
print("=" * 80)

cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'")
grand_total = cur.fetchone()[0]
print(f"  🌟 GRAND TOTAL LIBRARY DATABASE NOW: {grand_total} PURE CONFIRMED WAQIAT")
print("=" * 80)
conn.close()
