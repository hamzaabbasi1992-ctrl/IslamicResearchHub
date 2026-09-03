import sqlite3
conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()
try:
    cur.execute("SELECT * FROM Libraries LIMIT 5")
    print("Libraries:", cur.fetchall())
except Exception as e:
    print("Libraries error:", e)

# Test insert one by one
cols = [
    "BookID", "Source", "SourceBookID", "Title", "Author", "Publisher",
    "Language", "Category", "PageCount", "ChapterCount", "LibraryID",
    "AuthorID", "SeriesID", "VolumeNumber", "SourcePdfHint", "PublishYear"
]
for i in range(1, len(cols) + 1):
    subcols = cols[:i]
    placeholders = ", ".join(["?"] * len(subcols))
    vals = [95001, "src_test_1", "95001", "Title", "Author", "Pub", "ur", "33", 100, 1, 1, None, None, 1, None, None][:i]
    try:
        cur.execute(f"INSERT INTO Books ({', '.join(subcols)}) VALUES ({placeholders})", vals)
        conn.rollback()
        print(f"Success with {i} cols: {subcols[-1]}")
    except Exception as e:
        print(f"Failed at col {i} ({subcols[-1]}): {e}")

conn.close()
