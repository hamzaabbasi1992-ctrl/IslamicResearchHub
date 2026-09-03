import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

cur.execute("SELECT sql FROM sqlite_master WHERE name='Pages'")
print("Pages Table Schema:\n", cur.fetchone()[0])

cur.execute("PRAGMA index_list(Pages)")
print("\nPages Table Indices:\n", cur.fetchall())

conn.close()
