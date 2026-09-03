import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

cur.execute("SELECT LibraryID, Name FROM Libraries")
print("Available Libraries in data/books.db:")
for lid, name in cur.fetchall():
    print(f"  LibraryID {lid}: {name}")

print("\nRecent Books Library & Category Check:")
bids = [
    (3601, 3612, "خطبات حکیم العصر"),
    (3392, 4251, "اسلام اور ہماری زندگی"),
    (3534, 3567, "خطبات قاسمی")
]

for start_b, end_b, label in bids:
    cur.execute("SELECT BookID, Title, LibraryID, Category, SeriesID, VolumeNumber FROM Books WHERE BookID BETWEEN ? AND ? ORDER BY BookID", (start_b, end_b))
    rows = cur.fetchall()
    print(f"\n=== {label} ({len(rows)} books found) ===")
    for r in rows:
        print(f"  BookID {r[0]:5d} | {r[1]:32s} | LibID: {r[2]} | Cat: {r[3]} | SeriesID: {r[4]} | Vol: {r[5]}")

conn.close()
