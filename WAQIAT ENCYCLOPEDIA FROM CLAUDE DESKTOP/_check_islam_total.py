import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
bids = [3392, 3465, 3523, 3633, 3744, 3854, 3961, 4051, 4146, 4251]
bids_str = ",".join(str(b) for b in bids)

rows = conn.execute(f"""
    SELECT ec.BookID, b.Title, COUNT(*)
    FROM EventCandidates ec
    JOIN Books b ON ec.BookID = b.BookID
    WHERE ec.BookID IN ({bids_str}) AND ec.Status='confirmed'
    GROUP BY ec.BookID, b.Title
    ORDER BY ec.BookID
""").fetchall()

print("=" * 85)
print(" ISLAM AUR HAMARI ZINDAGI CONFIRMED WAQIAT BREAKDOWN ACROSS ALL 10 VOLUMES")
print("=" * 85)
total = 0
for bid, title, cnt in rows:
    total += cnt
    print(f"  BookID {bid:5d} | {title:34s} | {cnt:3d} Waqiat")
print("-" * 85)
print(f"  TOTAL CONFIRMED WAQIAT FOR ISLAM AUR HAMARI ZINDAGI: {total}")
print("=" * 85)

cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'")
grand_total = cur.fetchone()[0]
print(f"  🌟 GRAND TOTAL MASTER LIBRARY DATABASE NOW: {grand_total} PURE CONFIRMED WAQIAT")
print("=" * 85)
conn.close()
