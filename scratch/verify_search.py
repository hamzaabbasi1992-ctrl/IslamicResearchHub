"""End-to-end search verification after FTS fix."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import SqliteBookSearchRepository
from islamic_research_hub.application.book_search import BookSearchService

db = Path("data/books.db")
svc = BookSearchService(SqliteBookSearchRepository(db))

tests = ["إحياء", "hadith", "القرآن", "فقه", "prayer"]
for query in tests:
    try:
        res = svc.search(query, 10)
        status = f"✅ {len(res)} results"
        if res:
            status += f" | First: '{res[0].title}' (Book {res[0].book_id}, Page {res[0].page_number})"
    except Exception as e:
        status = f"❌ ERROR: {e}"
    print(f"[{query}] {status}")
