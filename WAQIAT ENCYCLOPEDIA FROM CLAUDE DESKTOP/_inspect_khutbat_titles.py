import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

for kw in ["مدنی", "حسنہ", "آزاد", "بہاولپور", "فقیر", "حکیم الاسلام", "طیب"]:
    cur.execute("SELECT BookID, Title, PageCount FROM Books WHERE Title LIKE ?", (f"%{kw}%",))
    rows = cur.fetchall()
    print(f"\nKeyword: '{kw}' ({len(rows)} books found)")
    for bid, title, pcount in rows[:10]:
        cur.execute("SELECT COUNT(*) FROM Pages WHERE BookID=? AND LENGTH(Content) > 50", (bid,))
        cpages = cur.fetchone()[0]
        print(f"  [{bid:5d}] {title[:45]} (Total Pgs: {pcount}, Content Pgs: {cpages})")

conn.close()
