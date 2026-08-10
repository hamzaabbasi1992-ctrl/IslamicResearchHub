# 🔧 Search & Categories Bug — Investigation Handover

**Project:** Islamic Research Hub AI  
**Workspace:** `F:\ISLAMIC RESEARCH HUB AI`  
**Date:** 2026-08-10  
**Handover to:** Claude Code (or any next session)

---

## 🎯 User's Reported Problems

1. **Categories tab shows nothing** in the Browse panel (left sidebar of the desktop app)
2. **Search returns "That search couldn't be run"** error for all queries

---

## 🔍 Root Cause Found

The database at `data/books.db` is a **compacted database** copied from a different build pipeline. It has a **schema mismatch** — the table names and structure differ from what the application code expects:

### Table Differences

| What code expects | What actually exists in `books.db` |
|---|---|
| `PagesFTS` (content-backed FTS with `content_rowid='rowid'`) | `Pages_fts` (snake_case, with `content_rowid='PageID'`) |
| `Categories` table (populated) | `Categories` table **existed but was EMPTY** |
| `CategoryTaxonomy` table (populated) | `CategoryTaxonomy` table **did not exist** |

### Why Search Fails

The search code in [`sqlite_book_search_repository.py`](file:///F:/ISLAMIC%20RESEARCH%20HUB%20AI/src/islamic_research_hub/infrastructure/persistence/sqlite_book_search_repository.py) at line ~108:

```python
use_normalized_index = not exact and self._index_exists(connection, "PagesFTSNormalized")
fts_table = "PagesFTSNormalized" if use_normalized_index else "PagesFTS"
```

It falls back to `PagesFTS` — but the actual table is called **`Pages_fts`** (with underscore). The table `PagesFTS` now **exists** (created by `_connect_read_only` migration baseline) but **is empty** (it's a content-backed FTS pointing to `Pages.PageID` as `content_rowid`, but was never populated).

So every search query hits `PagesFTS` which returns 0 rows.

### Why Categories Show Nothing

The `Categories` and `CategoryTaxonomy` tables were missing / empty. Without them:
- `get_category_tree()` returns an empty tuple → no nodes shown in the tree
- `_normalize_categories()` migration (migration 3) crashes with `no such table: Categories`

---

## ✅ Changes Already Made

### 1. `sqlite_book_search_repository.py` — FTS table fallback (DONE)

**File:** [`src/islamic_research_hub/infrastructure/persistence/sqlite_book_search_repository.py`](file:///F:/ISLAMIC%20RESEARCH%20HUB%20AI/src/islamic_research_hub/infrastructure/persistence/sqlite_book_search_repository.py)

Added `Pages_fts` as a fallback in `_search_content()` at ~line 108:

```python
# Before (broken):
use_normalized_index = not exact and self._index_exists(connection, "PagesFTSNormalized")
fts_table = "PagesFTSNormalized" if use_normalized_index else "PagesFTS"

# After (fixed):
if not exact and self._index_exists(connection, "PagesFTSNormalized"):
    fts_table = "PagesFTSNormalized"
elif self._index_exists(connection, "PagesFTS"):
    fts_table = "PagesFTS"
elif self._index_exists(connection, "Pages_fts"):
    fts_table = "Pages_fts"
else:
    fts_table = "PagesFTS"
use_normalized_index = fts_table == "PagesFTSNormalized"
```

**Problem:** Search still returns 0 results even after this fix. See **Remaining Issue** below.

### 2. Categories/CategoryTaxonomy tables created and backfilled (DONE via script)

These tables were created and populated with a simple backfill from `Books.Category`:

```python
# Categories backfill:
INSERT INTO Categories (BookID, Name)
SELECT BookID, Category FROM Books WHERE Category IS NOT NULL AND TRIM(Category) != ''

# CategoryTaxonomy backfill (flat, no hierarchy):
INSERT INTO CategoryTaxonomy (MJCN, Name, ParentMJCN)
SELECT ROW_NUMBER() OVER (ORDER BY Category), Category, 0
FROM (SELECT DISTINCT Category FROM Books WHERE Category IS NOT NULL AND TRIM(Category) != '')
```

This produces **655 category nodes** loaded into the tree. However, the category names are currently numeric MJCN codes (e.g. `'630'`, `'56'`). They should be Arabic/Urdu category names — they come from Jibreel `.mjbz` book data and should have been populated during import by `MasterBookRepository._import_book()`.

---

## ❌ Remaining Issue — Search Still Returns 0

Despite the code fix, `BookSearchService.search()` returns 0 results for any query.

### What We Know

- `Pages_fts` table **exists** and **has data**: 
  ```
  SELECT rowid FROM Pages_fts WHERE Pages_fts MATCH 'إحياء' LIMIT 5
  → Returns 5 rows
  ```
- Direct SQL query **works** when using a plain `sqlite3.connect()`:
  ```python
  conn = sqlite3.connect("data/books.db")
  # Search SQL with Pages_fts → Returns 20 results ✅
  ```
- `PagesFTS` table also **exists** but behaviour is unclear — might be empty (content-backed FTS never populated)
- The `_index_exists()` check detects **both** `Pages_fts` AND `PagesFTS` as existing

### Key Suspicion — `PagesFTS` is detected first, but is empty

The fixed code checks `PagesFTS` before `Pages_fts`:
```python
elif self._index_exists(connection, "PagesFTS"):
    fts_table = "PagesFTS"  # ← This is chosen, but might be empty!
elif self._index_exists(connection, "Pages_fts"):
    fts_table = "Pages_fts"
```

Since **both `PagesFTS` and `Pages_fts` exist**, the code picks `PagesFTS` first. But `PagesFTS` was created by the migration baseline as a content-backed FTS (`content='Pages', content_rowid='PageID'`) — and may never have been populated.

### Fix Needed

**Option A (Quick fix):** Swap the priority — check `Pages_fts` before `PagesFTS`:
```python
elif self._index_exists(connection, "Pages_fts"):
    fts_table = "Pages_fts"
elif self._index_exists(connection, "PagesFTS"):
    fts_table = "PagesFTS"
```

**Option B (Proper fix):** Run the full database migration to rebuild `PagesFTS` from `Pages`:
```bash
python -m islamic_research_hub.interfaces.migrate_database_cli --database data/books.db
```
⚠️ Migration fails at migration 3 (`_normalize_categories`) because `Categories` table needs to exist first.

**Option C (Proper proper fix):** Understand that the compacted `books.db` uses a different schema (`Pages_fts` with `PageID` as primary key, not `rowid`). The join in the search query uses `Pages.rowid = Pages_fts.rowid` but should use `Pages.PageID = Pages_fts.rowid`.

---

## 📋 Database Schema Reality

```sql
-- Actual Pages table (NOT what the code was written for)
CREATE TABLE Pages (
    PageID INTEGER PRIMARY KEY,   ← named primary key, not rowid
    BookID INTEGER,
    PageNo INTEGER,
    Content TEXT,
    HadeesNumber INTEGER,
    AyahNumber INTEGER,
    FOREIGN KEY (BookID) REFERENCES Books (BookID) ON DELETE CASCADE
)

-- Actual Pages_fts table
CREATE VIRTUAL TABLE Pages_fts USING fts5(
    Content,
    content='Pages',
    content_rowid='PageID'   ← maps to PageID, not rowid
)

-- What code expects (PagesFTS)  
CREATE VIRTUAL TABLE PagesFTS USING fts5(
    Content,
    content='Pages',
    content_rowid='PageID'   ← same definition, but was never populated
)
```

The join `JOIN Pages ON Pages.rowid = Pages_fts.rowid` is **correct** because SQLite's `rowid` is the same as `PageID` (it's declared as `INTEGER PRIMARY KEY` which aliases to `rowid`). So the join is fine.

---

## 🛠️ What To Do Next (Prioritized)

### Step 1: Fix search (15 mins)

In [`sqlite_book_search_repository.py`](file:///F:/ISLAMIC%20RESEARCH%20HUB%20AI/src/islamic_research_hub/infrastructure/persistence/sqlite_book_search_repository.py) line ~108, **swap the priority** of `Pages_fts` vs `PagesFTS`:

```python
if not exact and self._index_exists(connection, "PagesFTSNormalized"):
    fts_table = "PagesFTSNormalized"
elif self._index_exists(connection, "Pages_fts"):   # ← Put Pages_fts FIRST
    fts_table = "Pages_fts"
elif self._index_exists(connection, "PagesFTS"):     # ← Then fall back to PagesFTS
    fts_table = "PagesFTS"
else:
    fts_table = "PagesFTS"
use_normalized_index = fts_table == "PagesFTSNormalized"
```

Then verify:
```bash
python -c "from pathlib import Path; from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import SqliteBookSearchRepository; from islamic_research_hub.application.book_search import BookSearchService; svc = BookSearchService(SqliteBookSearchRepository(Path('data/books.db'))); res = svc.search('إحياء', 20); print('Results:', len(res), res[0].title)"
```

### Step 2: Fix categories showing numeric codes (30-60 mins)

The 655 categories in the tree show numeric MJCN codes (`630`, `56`, etc.) instead of Arabic names. The proper fix is:

1. Check if the original Jibreel source `.mjbz` files are available
2. Re-run the importer with categories, OR
3. Load a `CategoryTaxonomy` CSV/Excel mapping (if available) and populate from that

### Step 3: Run database migration (after Step 1+2)

```bash
python -m islamic_research_hub.interfaces.migrate_database_cli --database data/books.db
```

This will add `PagesFTSNormalized` (diacritic-tolerant Arabic search), `BooksFTS` (title search), author counts, etc.

---

## 📁 Key Files

| File | Purpose |
|---|---|
| [`src/.../sqlite_book_search_repository.py`](file:///F:/ISLAMIC%20RESEARCH%20HUB%20AI/src/islamic_research_hub/infrastructure/persistence/sqlite_book_search_repository.py) | Full-text search — where the FTS table name fix is needed |
| [`src/.../book_browser_repository.py`](file:///F:/ISLAMIC%20RESEARCH%20HUB%20AI/src/islamic_research_hub/infrastructure/persistence/book_browser_repository.py) | Category tree, author list, library browsing |
| [`src/.../migration_runner.py`](file:///F:/ISLAMIC%20RESEARCH%20HUB%20AI/src/islamic_research_hub/infrastructure/persistence/migration_runner.py) | Database migrations (16+ migrations) |
| [`src/.../master_book_repository.py`](file:///F:/ISLAMIC%20RESEARCH%20HUB%20AI/src/islamic_research_hub/infrastructure/persistence/master_book_repository.py) | Import pipeline — creates original schema |
| [`src/.../search_screen.py`](file:///F:/ISLAMIC%20RESEARCH%20HUB%20AI/src/islamic_research_hub/interfaces/desktop_app/search_screen.py) | Desktop app search UI |
| `data/books.db` | The master database (36,249 books) |

---

## 🧪 Quick Diagnostic Commands

```bash
# Check what FTS tables exist
python -c "import sqlite3; conn = sqlite3.connect('data/books.db'); print([r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE name LIKE \'%FTS%\' OR name LIKE \'%fts%\'').fetchall()])"

# Test direct FTS search
python -c "import sqlite3; conn = sqlite3.connect('data/books.db'); print(len(conn.execute('SELECT rowid FROM Pages_fts WHERE Pages_fts MATCH ? LIMIT 20', ['إحياء']).fetchall()), 'hits')"

# Test BookSearchService end-to-end
python -c "from pathlib import Path; from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import SqliteBookSearchRepository; from islamic_research_hub.application.book_search import BookSearchService; svc = BookSearchService(SqliteBookSearchRepository(Path('data/books.db'))); res = svc.search('إحياء', 20); print('Results:', len(res))"

# Check category count
python -c "import sqlite3; conn = sqlite3.connect('data/books.db'); print('Categories:', conn.execute('SELECT COUNT(*) FROM Categories').fetchone()[0], 'CategoryTaxonomy:', conn.execute('SELECT COUNT(*) FROM CategoryTaxonomy').fetchone()[0])"

# Run full migration
python -m islamic_research_hub.interfaces.migrate_database_cli --database data/books.db
```

---

## 🗒️ Notes

- The compacted `books.db` (24.5 GB on D: drive, now on F: drive) came from a different build run. Its `Pages` table uses `PageID` as a named primary key and `Pages_fts` as the FTS table name — while the current codebase was written expecting `PagesFTS` pointing to `rowid`.
- The migration system uses `PRAGMA user_version` to track state. The current `user_version` of the db may be at 1 or 2 (stopped at migration 3 due to missing `Categories` table).
- All 36,249 books have pages and are readable. Only search and category browsing are broken.
