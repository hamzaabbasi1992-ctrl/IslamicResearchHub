import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

for bid in [3392, 3465, 3523]:
    cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=? AND PageNo IN (5, 25, 50, 100)", (bid,))
    rows = cur.fetchall()
    print(f"=== BookID {bid} Pages Sample ===")
    for pno, content in rows:
        c_len = len(content) if content else 0
        preview = repr(content[:100]) if content else "EMPTY"
        print(f"  Page {pno:3d} (Len: {c_len:4d}): {preview}")
    print()

conn.close()
