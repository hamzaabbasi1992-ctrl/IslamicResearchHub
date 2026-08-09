import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
db_path = Path("data/books.db")

with sqlite3.connect(db_path) as conn:
    conn.execute("PRAGMA auto_vacuum;")
    av_mode = conn.execute("PRAGMA auto_vacuum;").fetchone()[0]
    freelist_cnt = conn.execute("PRAGMA freelist_count;").fetchone()[0]

print(f"Current Auto-Vacuum Mode: {av_mode} (0=NONE, 1=FULL, 2=INCREMENTAL)")
print(f"Freelist Pages: {freelist_cnt:,}")
