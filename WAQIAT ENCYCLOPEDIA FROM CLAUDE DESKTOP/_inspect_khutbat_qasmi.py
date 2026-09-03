import os, sys, glob, pymupdf, sqlite3
sys.stdout.reconfigure(encoding='utf-8')

qasmi_dir = r"F:\کتب\خطبات و مواعظ ۔\خطبات قاسمی"
print("=" * 85)
print(" INSPECTING KHUTBAT QASMI")
print("=" * 85)

pdf_files = sorted(glob.glob(os.path.join(qasmi_dir, "*.pdf")) + glob.glob(os.path.join(qasmi_dir, "**", "*.pdf"), recursive=True))
print(f"Total PDFs found: {len(pdf_files)}")

for p in pdf_files:
    fname = os.path.basename(p)
    doc = pymupdf.open(p)
    print(f"  📄 {fname:45s} | Pages: {len(doc):4d}")
    
    # Check sample text on page 20, 50, 100
    for pidx in [10, 25, 50, 100, 200, 500]:
        if pidx < len(doc):
            txt = doc[pidx].get_text().strip()
            print(f"     Sample Page {pidx+1}: {len(txt)} chars | Starts: {txt[:60].replace(chr(10), ' ')}")
            
    toc = doc.get_toc()
    print(f"     TOC Bookmarks: {len(toc)}")
    if toc:
        print("     --- First 10 TOC Entries ---")
        for item in toc[:10]:
            print(f"       Level {item[0]} | Page {item[2]} | {item[1]}")
    doc.close()

print("\n" + "=" * 85)
print(" CHECKING BOOKS TABLE IN books.db FOR KHUTBAT QASMI")
print("=" * 85)
conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()
cur.execute("SELECT BookID, Title, Author, PageCount, VolumeNumber FROM Books WHERE Title LIKE '%قاسمی%' OR Title LIKE '%قاسمیہ%'")
rows = cur.fetchall()
print(f"Found {len(rows)} matching records in Books table:")
for r in rows:
    print(f"  BookID: {r[0]:6d} | Title: {r[1]:45s} | Author: {r[2]} | Vol: {r[4]}")
conn.close()
print("=" * 85)
