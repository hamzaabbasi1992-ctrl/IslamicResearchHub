import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()
cur.execute("SELECT sql FROM sqlite_master WHERE name='Books'")
print("Books Schema:")
print(cur.fetchone()[0])
conn.close()
