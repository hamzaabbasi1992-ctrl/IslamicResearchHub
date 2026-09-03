import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
bids = [4362, 4473, 4583, 4594, 4604, 4629, 4680, 4761]
bids_str = ",".join(str(b) for b in bids)

rows = conn.execute(f"SELECT BookID, COUNT(*), MAX(LENGTH(Content)) FROM Pages WHERE BookID IN ({bids_str}) GROUP BY BookID").fetchall()
print("Existing Pages for Islahi Taqreerain:")
for bid, cnt, max_len in rows:
    print(f"  BookID {bid}: {cnt} pages, Max Content Length: {max_len}")

conn.close()
