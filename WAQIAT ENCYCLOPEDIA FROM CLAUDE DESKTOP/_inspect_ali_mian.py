import os, sys, glob, fitz, sqlite3
sys.stdout.reconfigure(encoding='utf-8')

ali_dir = r"F:\کتب\خطبات و مواعظ ۔\خطباتِ علی میاں ۔"
print("=" * 85)
print(" INSPECTING KHUTBAT ALI MIAN PDFS")
print("=" * 85)

pdf_files = sorted(glob.glob(os.path.join(ali_dir, "*.pdf")) + glob.glob(os.path.join(ali_dir, "**", "*.pdf"), recursive=True))
print(f"Total PDFs Found: {len(pdf_files)}")

for p in pdf_files:
    fname = os.path.basename(p)
    size_mb = os.path.getsize(p) / (1024 * 1024)
    try:
        doc = fitz.open(p)
        print(f"  📄 {fname:50s} | {size_mb:6.2f} MB | {len(doc):4d} pages")
        doc.close()
    except Exception as e:
        print(f"  ❌ {fname:50s} | Error: {e}")

print("\n" + "=" * 85)
print(" CHECKING BOOKS TABLE IN books.db FOR KHUTBAT ALI MIAN")
print("=" * 85)
conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()
cur.execute("SELECT BookID, Title, Author, PageCount, VolumeNumber FROM Books WHERE Title LIKE '%علی میاں%' OR Title LIKE '%ندوی%' OR Title LIKE '%خطبات%علی%'")
rows = cur.fetchall()
print(f"Found {len(rows)} matching records in Books table:")
for r in rows:
    print(f"  BookID: {r[0]:6d} | Title: {r[1]:45s} | Author: {r[2]} | Vol: {r[4]}")
conn.close()
print("=" * 85)
