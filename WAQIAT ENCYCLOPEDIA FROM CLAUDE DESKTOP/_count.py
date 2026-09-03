import sqlite3
conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
total = conn.execute("SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'").fetchone()[0]
print("CURRENT TOTAL:", total)
conn.close()
