import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

# Get all books with confirmed waqiat counts
cur.execute("SELECT BookID, COUNT(*) FROM EventCandidates WHERE Status='confirmed' GROUP BY BookID")
cand_map = dict(cur.fetchall())

# Find all books with > 10 pages of text in DB
cur.execute("""
    SELECT b.BookID, b.Title, b.Author, b.PageCount
    FROM Books b
    WHERE b.PageCount > 5
    ORDER BY b.BookID
""")
all_books = cur.fetchall()

candidates = []

for bid, title, author, pcount in all_books:
    if bid == 545 or 'فضائل اعمال' in title:
        continue

    # Fast page count check
    cur.execute("SELECT COUNT(*) FROM Pages WHERE BookID=? AND LENGTH(Content) > 50", (bid,))
    cpages = cur.fetchone()[0]
    if cpages < 10:
        continue

    conf = cand_map.get(bid, 0)
    cov = (conf / cpages * 100) if cpages else 0

    if cov < 40:
        candidates.append({
            'bid': bid,
            'title': title,
            'author': author or '',
            'cpages': cpages,
            'conf': conf,
            'cov': cov
        })

print("=" * 85)
print(f" REMAINING HIGH-POTENTIAL CANDIDATE BOOKS ({len(candidates)} Books)")
print("=" * 85)
print(f"{'BookID':>7} | {'Confirmed':>9} | {'ContentPgs':>10} | {'Coverage%':>9} | Title (Author)")
print("-" * 85)

for c in sorted(candidates, key=lambda x: -x['cpages']):
    print(f"{c['bid']:>7} | {c['conf']:>9} | {c['cpages']:>10} | {c['cov']:>8.1f}% | {c['title'][:45]} ({c['author'][:20]})")

conn.close()
