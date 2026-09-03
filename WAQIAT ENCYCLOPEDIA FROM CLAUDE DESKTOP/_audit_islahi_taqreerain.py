import os, sys, sqlite3, pymupdf, json
sys.stdout.reconfigure(encoding='utf-8')

FOLDER = r"F:\کتب\خطبات و مواعظ ۔\اصلاحی تقریریں ۔"
DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

print("=" * 85)
print(" PRE-INGESTION AUDIT: ISLAHI TAQREERAIN (مفتی محمد رفیع عثمانیؒ — 9 جلدیں)")
print("=" * 85)

files = [f for f in os.listdir(FOLDER) if f.lower().endswith(('.pdf', '.docx'))]
print(f"Files found in folder: {len(files)}")
for f in files:
    fpath = os.path.join(FOLDER, f)
    sz = os.path.getsize(fpath) / (1024 * 1024)
    print(f"  📄 {f} ({sz:.2f} MB)")

master_pdf = os.path.join(FOLDER, "اصلاحی تقریریں مع فہرست 9 جلدیں م رفیع عثمانی.pdf")
if not os.path.exists(master_pdf):
    print(f"❌ Master PDF not found: {master_pdf}")
    sys.exit(1)

doc = pymupdf.open(master_pdf)
pcount = len(doc)
print(f"\nMaster PDF Total Pages: {pcount}")

sample_text = ""
for p in range(min(15, pcount)):
    sample_text += doc[p].get_text()

has_text_layer = len(sample_text.strip()) > 200
print(f"Has Embedded Text Layer: {has_text_layer}")

toc = doc.get_toc()
print(f"Total Outlines / Bookmarks: {len(toc)}")

print("\n--- Volume Bookmarks & Milestones ---")
vol_landmarks = []
for item in toc:
    lvl, title, pno = item
    if lvl == 1 or 'جلد' in title or 'VOL' in title.upper():
        print(f"  Bookmark [Lvl {lvl}]: {title[:50]:50s} -> PDF Page {pno}")
        vol_landmarks.append((title, pno))

doc.close()

# Database Check
print("\n" + "=" * 85)
print(" CHECKING DATA/BOOKS.DB FOR EXISTING ENTRIES")
print("=" * 85)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT BookID, Title, Author, PageCount, VolumeNumber FROM Books WHERE Title LIKE '%اصلاحی تقریریں%' ORDER BY BookID")
rows = cur.fetchall()
print(f"Existing Books with 'اصلاحی تقریریں': {len(rows)}")
for r in rows:
    print(f"  BookID {r[0]:5d} | {r[1]:32s} | {r[2]} | Pages: {r[3]} | Vol: {r[4]}")

cur.execute("""
    SELECT ec.BookID, b.Title, COUNT(*)
    FROM EventCandidates ec
    JOIN Books b ON ec.BookID = b.BookID
    WHERE b.Title LIKE '%اصلاحی تقریریں%'
    GROUP BY ec.BookID, b.Title
""")
w_rows = cur.fetchall()
print(f"\nExisting Waqiat for 'اصلاحی تقریریں': {len(w_rows)}")
for w in w_rows:
    print(f"  BookID {w[0]} | {w[1]} | {w[2]} Waqiat")

conn.close()
