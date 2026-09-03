import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
rows = conn.execute("SELECT BookID, Title, VolumeNumber, PageCount FROM Books WHERE Title LIKE '%خطبات قاسمی%'").fetchall()
print("Matches in Books table for 'خطبات قاسمی':")
for r in rows:
    print(" ", r)

if not rows:
    # Check what BookIDs are free around 5200 or 96000
    cur = conn.cursor()
    cur.execute("SELECT MAX(BookID) FROM Books WHERE BookID < 90000")
    print("Max BookID below 90000:", cur.fetchone()[0])

conn.close()
