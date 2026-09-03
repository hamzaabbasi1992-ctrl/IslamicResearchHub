import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

for p in range(1, 26):
    cur.execute("SELECT Content FROM Pages WHERE BookID=3392 AND PageNo=?", (p,))
    r = cur.fetchone()
    txt = r[0] if r else ""
    first_line = txt.split('\n')[0] if txt else "EMPTY"
    has_fihrist = "فہرست" in txt or "صفحہ نمبر" in txt
    print(f"Page {p:2d}: has_fihrist={has_fihrist} | {first_line[:60]}")

conn.close()
