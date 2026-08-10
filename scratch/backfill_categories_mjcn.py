"""Backfill Categories.MJCN from CategoryTaxonomy.Name for the ad-hoc
backfilled rows that only ever got Name set (see HANDOVER.md)."""
import sqlite3
from pathlib import Path

db = Path("data/books.db")
conn = sqlite3.connect(db)

before = conn.execute("SELECT COUNT(*) FROM Categories WHERE MJCN IS NULL").fetchone()[0]
print(f"Categories with NULL MJCN before: {before}")

conn.execute(
    """
    UPDATE Categories
    SET MJCN = (SELECT t.MJCN FROM CategoryTaxonomy t WHERE t.Name = Categories.Name)
    WHERE MJCN IS NULL
    """
)
conn.commit()

after = conn.execute("SELECT COUNT(*) FROM Categories WHERE MJCN IS NULL").fetchone()[0]
print(f"Categories with NULL MJCN after: {after}")
conn.close()
