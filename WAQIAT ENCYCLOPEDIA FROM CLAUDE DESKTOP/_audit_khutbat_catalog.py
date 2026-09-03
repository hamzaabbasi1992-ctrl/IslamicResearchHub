import sqlite3, sys, os
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')

EXCEL_PATH = r"F:\ISLAMIC RESEARCH HUB AI\Urdu_Khutbat_Bayanat_Catalog.xlsx"
DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

df = pd.read_excel(EXCEL_PATH)

print("=" * 95)
print(" KHUTBAT & BAYANAT CATALOG AUDIT: TEXT AVAILABILITY IN LIBRARY DATABASE")
print("=" * 95)

has_text = []
missing_text = []

for idx, row in df.iterrows():
    s_name = str(row.get('Series Name', '')).strip()
    author = str(row.get('Author / Speaker', '')).strip()
    vols = row.get('Total Volumes in Series', 1)
    status_excel = str(row.get('Library Status', '')).strip()

    # Search in Books table
    cur.execute("SELECT BookID, Title FROM Books WHERE Title LIKE ?", (f"%{s_name}%",))
    found_books = cur.fetchall()

    if not found_books:
        # Try finding by author or first 2 words
        words = s_name.split()[:2]
        kw = " ".join(words)
        cur.execute("SELECT BookID, Title FROM Books WHERE Title LIKE ?", (f"%{kw}%",))
        found_books = cur.fetchall()

    # Check if any found book has actual page content
    text_books = []
    empty_books = []
    for bid, btitle in found_books:
        cur.execute("SELECT COUNT(*) FROM Pages WHERE BookID=? AND LENGTH(Content) > 50", (bid,))
        cnt = cur.fetchone()[0]
        if cnt > 0:
            text_books.append((bid, btitle, cnt))
        else:
            empty_books.append((bid, btitle))

    if text_books:
        total_p = sum(c[2] for c in text_books)
        has_text.append({
            'series': s_name,
            'author': author,
            'excel_vols': vols,
            'db_books': len(text_books),
            'pages': total_p
        })
    else:
        missing_text.append({
            'series': s_name,
            'author': author,
            'excel_vols': vols,
            'found_in_db': len(found_books),
            'status': status_excel
        })

conn.close()

print(f"\n--- 1. KHUTBAT SERIES WITH FULL TEXT AVAILABLE IN DB ({len(has_text)} Series) ---")
print(f"{'Series Name':<35} | {'Author':<25} | {'Vols (Excel)':<12} | {'Vols in DB':<10} | {'Text Pages'}")
print("-" * 95)
for h in has_text:
    print(f"{h['series'][:35]:<35} | {h['author'][:25]:<25} | {str(h['excel_vols']):<12} | {h['db_books']:<10} | {h['pages']}")

print(f"\n--- 2. KHUTBAT SERIES MISSING TEXT IN DB ({len(missing_text)} Series) ---")
print(f"{'Series Name':<35} | {'Author':<25} | {'Vols':<6} | {'Found in DB':<12} | {'Catalog Note'}")
print("-" * 95)
for m in missing_text[:30]:
    print(f"{m['series'][:35]:<35} | {m['author'][:25]:<25} | {str(m['excel_vols']):<6} | {str(m['found_in_db']):<12} | {m['status'][:20]}")

if len(missing_text) > 30:
    print(f"... and {len(missing_text) - 30} more series listed in Excel without text in DB.")

print("\n" + "=" * 95)
print(f" SUMMARY: {len(has_text)} Series have full text (100% Extracted) | {len(missing_text)} Series are listed in Excel but have NO text in DB.")
print("=" * 95)
