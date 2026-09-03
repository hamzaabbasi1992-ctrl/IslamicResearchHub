import os, sys, sqlite3, pymupdf, json
sys.stdout.reconfigure(encoding='utf-8')

FOLDER = r"F:\کتب\خطبات و مواعظ ۔\اسلام اور ہماری زندگی م تقی عثمانی"
DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

print("=" * 85)
print(" PRE-INGESTION AUDIT: ISLAM AUR HAMARI ZINDAGI (مفتی محمد تقی عثمانی مدظلہم)")
print("=" * 85)

if not os.path.exists(FOLDER):
    print(f"❌ Error: Folder does not exist: {FOLDER}")
    sys.exit(1)

files = [f for f in os.listdir(FOLDER) if f.lower().endswith('.pdf')]
files.sort()
print(f"Total PDF Files found in folder: {len(files)}\n")

total_pages = 0
pdf_details = []

for idx, f in enumerate(files, 1):
    fpath = os.path.join(FOLDER, f)
    fsize_mb = os.path.getsize(fpath) / (1024 * 1024)
    doc = pymupdf.open(fpath)
    pcount = len(doc)
    total_pages += pcount

    sample_text = ""
    for p in range(min(10, pcount)):
        sample_text += doc[p].get_text()

    has_text_layer = len(sample_text.strip()) > 200
    is_unicode = False
    is_inpage = False
    sample_chars = sample_text.strip()[:100]

    if has_text_layer:
        urdu_chars = sum(1 for c in sample_text if '\u0600' <= c <= '\u06FF')
        if urdu_chars > 100:
            is_unicode = True
        else:
            is_inpage = True

    pdf_details.append({
        'filename': f,
        'path': fpath,
        'size_mb': fsize_mb,
        'pages': pcount,
        'has_text_layer': has_text_layer,
        'is_unicode': is_unicode,
        'is_inpage': is_inpage,
        'sample_preview': sample_chars
    })
    doc.close()

    print(f"[{idx:2d}] {f}")
    print(f"     حجم: {fsize_mb:6.2f} MB | صفحات: {pcount:4d}")
    print(f"     ٹیکسٹ لیئر: {'موجود' if has_text_layer else 'موجود نہیں (خالص اسکین)'} | یونیکوڈ: {is_unicode} | ان پیج: {is_inpage}")
    if has_text_layer:
        print(f"     نمونہ: {repr(sample_chars[:40])}")
    print()

print("-" * 85)
print(f"مجموعی صفحات (Grand Total Pages): {total_pages:,} صفحات")
print("=" * 85)

# 2. Database Audit
print("\n--- DATABASE AUDIT IN DATA/BOOKS.DB ---")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT BookID, Title, Author, PageCount, VolumeNumber FROM Books WHERE Title LIKE '%اسلام اور ہماری زندگی%'")
existing_books = cur.fetchall()
print(f"Existing Books related to 'اسلام اور ہماری زندگی': {len(existing_books)}")
for b in existing_books:
    print(f"  BookID {b[0]} | {b[1]} | {b[2]} | {b[3]} pgs | Vol {b[4]}")

cur.execute("""
    SELECT ec.BookID, b.Title, COUNT(*)
    FROM EventCandidates ec
    JOIN Books b ON ec.BookID = b.BookID
    WHERE b.Title LIKE '%اسلام اور ہماری زندگی%'
    GROUP BY ec.BookID, b.Title
""")
existing_waqiat = cur.fetchall()
print(f"\nExisting Waqiat for 'اسلام اور ہماری زندگی': {len(existing_waqiat)}")
for w in existing_waqiat:
    print(f"  BookID {w[0]} | {w[1]} | {w[2]} Waqiat")

conn.close()
