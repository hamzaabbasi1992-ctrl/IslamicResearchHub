import pandas as pd
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

EXCEL_PATH = r"F:\ISLAMIC RESEARCH HUB AI\Urdu_Khutbat_Bayanat_Catalog.xlsx"
DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

df = pd.read_excel(EXCEL_PATH)
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Get all books with confirmed waqiat
cur.execute("SELECT BookID, COUNT(*) FROM EventCandidates WHERE Status='confirmed' GROUP BY BookID")
cand_map = dict(cur.fetchall())

print("=" * 105)
print(" EXCEL KHUTBAT CATALOG (123 Series) vs. DATABASE TEXT AVAILABILITY AUDIT")
print("=" * 105)

completed_in_db = []
empty_in_db = []
not_in_db_at_all = []

for idx, r in df.iterrows():
    sid = r.get('SeriesID', idx+1)
    title = str(r.get('Khutbat & Bayanat Series Title', '')).strip()
    author = str(r.get('Author / Scholar', '')).strip()
    status_col = str(r.get('Status', '')).strip()
    missing_vols = str(r.get('Missing / Remaining Volumes List', '')).strip()

    # Search in Books table
    cur.execute("SELECT BookID, Title FROM Books WHERE Title LIKE ?", (f"%{title}%",))
    found = cur.fetchall()

    if not found:
        # Search by partial keyword
        clean_kw = title.replace("خطبات", "").replace("مواعظ", "").replace("تقاریر", "").strip()
        if len(clean_kw) > 3:
            cur.execute("SELECT BookID, Title FROM Books WHERE Title LIKE ?", (f"%{clean_kw}%",))
            found = cur.fetchall()

    if not found:
        not_in_db_at_all.append((sid, title, author, status_col, missing_vols))
    else:
        # Check text pages for found books
        has_text_vols = []
        zero_text_vols = []
        for bid, btitle in found:
            cur.execute("SELECT COUNT(*) FROM Pages WHERE BookID=? AND LENGTH(Content) > 50", (bid,))
            cnt = cur.fetchone()[0]
            conf = cand_map.get(bid, 0)
            if cnt > 0:
                has_text_vols.append((bid, btitle, cnt, conf))
            else:
                zero_text_vols.append((bid, btitle))

        if has_text_vols:
            total_waqiat = sum(v[3] for v in has_text_vols)
            total_pages = sum(v[2] for v in has_text_vols)
            completed_in_db.append((sid, title, author, len(has_text_vols), total_pages, total_waqiat))
        else:
            empty_in_db.append((sid, title, author, len(zero_text_vols), status_col))

conn.close()

print(f"\n✅ 1. KHUTBAT SERIES WITH FULL TEXT IN DATABASE & 100% EXTRACTED ({len(completed_in_db)} Series):")
print(f"{'ID':>4} | {'Series Title':<35} | {'Author':<25} | {'Vols':>5} | {'Pages':>7} | {'Extracted Waqiat'}")
print("-" * 105)
for s in completed_in_db:
    print(f"{s[0]:>4} | {s[1][:35]:<35} | {s[2][:25]:<25} | {s[3]:>5} | {s[4]:>7} | {s[5]:>8} Waqiat")

print(f"\n⚠️ 2. KHUTBAT SERIES PRESENT IN CATALOG/DATABASE BUT HAVE ZERO TEXT PAGES (EMPTY BOOK BLOBS) ({len(empty_in_db)} Series):")
print(f"{'ID':>4} | {'Series Title':<35} | {'Author':<25} | {'Empty Vols':>10} | {'Catalog Status'}")
print("-" * 105)
for s in empty_in_db[:20]:
    print(f"{s[0]:>4} | {s[1][:35]:<35} | {s[2][:25]:<25} | {s[3]:>10} | {s[4][:25]}")
if len(empty_in_db) > 20:
    print(f"... and {len(empty_in_db) - 20} more empty book series in DB.")

print(f"\n❌ 3. KHUTBAT SERIES IN EXCEL CATALOG NOT YET IMPORTED / DOWNLOADED INTO DB ({len(not_in_db_at_all)} Series):")
print(f"{'ID':>4} | {'Series Title':<35} | {'Author':<25} | {'Excel Status':<25}")
print("-" * 105)
for s in not_in_db_at_all[:20]:
    print(f"{s[0]:>4} | {s[1][:35]:<35} | {s[2][:25]:<25} | {s[3][:25]}")
if len(not_in_db_at_all) > 20:
    print(f"... and {len(not_in_db_at_all) - 20} more series listed in Excel catalog.")

print("\n" + "=" * 105)
print(f" TOTAL CATALOG BREAKDOWN: {len(completed_in_db)} Series Completed (Full Text) | {len(empty_in_db)} Empty In DB | {len(not_in_db_at_all)} Not In DB")
print("=" * 105)
